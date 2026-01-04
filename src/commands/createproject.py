"""
Create project command for the Discord Copilot Bot.
"""

import re
import uuid
from datetime import datetime
from typing import Callable, Optional

import discord
from discord import app_commands

from ..config import (
    CLEANUP_AFTER_PUSH,
    MAX_PROMPT_LENGTH,
    MODEL_NAME_PATTERN,
    PROMPT_LOG_TRUNCATE_LENGTH,
    UNIQUE_ID_LENGTH,
    get_prompt_template,
)
from ..utils import (
    SessionLogCollector,
    count_files_excluding_ignored,
    github_manager,
    sanitize_username,
)
from ..utils.async_buffer import AsyncOutputBuffer
from ..utils.logging import logger
from ..utils.text_utils import format_error_message

# Import all helper functions for backward compatibility
from .createproject_helpers import (
    _build_unified_message,
    _generate_copilot_output_section,
    _generate_folder_structure_section,
    _generate_summary_section,
    _handle_remove_readonly,
    _send_log_file,
    cleanup_project_directory,
    create_project_directory,
    handle_github_integration,
    read_stream,
    run_copilot_process,
    send_initial_message,
    update_final_message,
    update_unified_message,
)

# Re-export for backward compatibility
__all__ = [
    "_build_unified_message",
    "_generate_copilot_output_section",
    "_generate_folder_structure_section",
    "_generate_summary_section",
    "_handle_remove_readonly",
    "_send_log_file",
    "cleanup_project_directory",
    "create_project_directory",
    "handle_github_integration",
    "read_stream",
    "run_copilot_process",
    "send_initial_message",
    "setup_createproject_command",
    "update_final_message",
    "update_unified_message",
]


def setup_createproject_command(bot) -> Callable:
    """Set up the /createproject command on the bot."""
    import asyncio
    import traceback

    from ..config import GITHUB_ENABLED

    @bot.tree.command(
        name="createproject", description="Create a new project using Copilot CLI"
    )
    @app_commands.describe(
        prompt="The prompt describing what project to create",
        model="Optional: The model to use (e.g., gpt-4, claude-3-opus)",
    )
    async def createproject(
        interaction: discord.Interaction,
        prompt: str,
        model: Optional[str] = None,
    ) -> None:
        """Handle the /createproject command."""
        # Validate prompt
        prompt = prompt.strip()
        if not prompt:
            await interaction.response.send_message(
                format_error_message(
                    "Invalid Input", "Prompt cannot be empty.", include_traceback=False
                ),
                ephemeral=True,
            )
            return

        if len(prompt) > MAX_PROMPT_LENGTH:
            await interaction.response.send_message(
                format_error_message(
                    "Invalid Input",
                    f"Prompt is too long (max {MAX_PROMPT_LENGTH:,} characters).",
                    include_traceback=False,
                ),
                ephemeral=True,
            )
            return

        # Validate model if provided
        if model and not re.match(MODEL_NAME_PATTERN, model):
            await interaction.response.send_message(
                format_error_message(
                    "Invalid Input",
                    "Invalid model name format. Use only letters, numbers, hyphens, underscores, and dots.",
                    include_traceback=False,
                ),
                ephemeral=True,
            )
            return

        await interaction.response.defer()

        # Acquire semaphore to limit parallel requests
        semaphore = bot.request_semaphore
        await semaphore.acquire()

        try:
            # Log GitHub configuration status
            logger.info(
                f"GitHub enabled: {GITHUB_ENABLED}, configured: {github_manager.is_configured()}"
            )

            # Create unique project folder
            username = sanitize_username(interaction.user.name)

            # Initialize session log collector
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            unique_id = str(uuid.uuid4())[:UNIQUE_ID_LENGTH]
            folder_name = f"{username}_{timestamp}_{unique_id}"

            session_log = SessionLogCollector(folder_name)
            session_log.info(f"User '{interaction.user.name}' started /createproject")
            session_log.info(
                f"Prompt: {prompt[:PROMPT_LOG_TRUNCATE_LENGTH]}{'...' if len(prompt) > PROMPT_LOG_TRUNCATE_LENGTH else ''}"
            )
            if model:
                session_log.info(f"Model: {model}")

            # Build full prompt with template prepended (user prompt is kept separate for display)
            prompt_template = get_prompt_template("createproject")
            if prompt_template:
                full_prompt = f"{prompt_template}\n\n{prompt}"
                session_log.info("Prompt template prepended from config.yaml")
            else:
                full_prompt = prompt

            # Create project directory (uses Azure OpenAI for creative naming if configured)
            try:
                project_path, folder_name = await create_project_directory(
                    username, session_log, prompt
                )
            except Exception as e:
                session_log.error(f"Failed to create project directory: {e}")
                await interaction.followup.send(
                    format_error_message(
                        "Failed to create project directory", traceback.format_exc()
                    )
                )
                return

            # Send initial unified message
            try:
                unified_msg = await send_initial_message(
                    interaction, project_path, prompt, model
                )
            except Exception as e:
                session_log.error(f"Failed to send Discord message: {e}")
                await interaction.followup.send(
                    format_error_message(
                        "Failed to send message", traceback.format_exc()
                    )
                )
                return

            # State tracking with thread-safe buffer
            output_buffer = AsyncOutputBuffer()
            is_running = asyncio.Event()
            is_running.set()
            error_event = asyncio.Event()

            # Start unified update task (single 3-second timer for all sections)
            unified_task = asyncio.create_task(
                update_unified_message(
                    unified_msg,
                    project_path,
                    output_buffer,
                    interaction,
                    prompt,
                    model,
                    is_running,
                    error_event,
                )
            )

            try:
                # Run the copilot process with full prompt (includes template)
                (
                    timed_out,
                    error_occurred,
                    error_message,
                    process,
                ) = await run_copilot_process(
                    project_path,
                    full_prompt,
                    model,
                    session_log,
                    output_buffer,
                    is_running,
                    error_event,
                )
            finally:
                is_running.clear()

                # Wait for update task to finish
                unified_task.cancel()
                try:
                    await unified_task
                except asyncio.CancelledError:
                    pass

            # Handle GitHub integration
            (
                github_status,
                github_success,
                repo_description,
                github_url,
            ) = await handle_github_integration(
                project_path,
                folder_name,
                prompt,
                timed_out,
                error_occurred,
                process,
                session_log,
            )

            # Final update to unified message with complete status
            await update_final_message(
                unified_msg,
                project_path,
                output_buffer,
                interaction,
                prompt,
                model,
                timed_out,
                error_occurred,
                error_message,
                process,
                github_status,
                project_name=folder_name,
                description=repo_description,
                github_url=github_url,
            )

            # Count files created (excluding ignored folders)
            file_count, dir_count = count_files_excluding_ignored(project_path)

            # Send log file attachment
            await _send_log_file(
                interaction,
                session_log,
                folder_name,
                prompt,
                model,
                timed_out,
                error_occurred,
                error_message,
                process,
                file_count,
                dir_count,
                output_buffer,
            )

            # Cleanup local project directory after successful GitHub push
            if CLEANUP_AFTER_PUSH and github_success:
                cleanup_project_directory(project_path, session_log)
        finally:
            semaphore.release()

    return createproject
