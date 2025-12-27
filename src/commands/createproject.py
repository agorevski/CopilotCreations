"""
Create project command for the Discord Copilot Bot.
"""

import asyncio
import io
import re
import traceback
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, Callable, Tuple

import discord
from discord import app_commands

from ..config import (
    PROJECTS_DIR,
    TIMEOUT_SECONDS,
    UPDATE_INTERVAL,
    MAX_MESSAGE_LENGTH,
    COPILOT_DEFAULT_FLAGS,
    PROMPT_LOG_TRUNCATE_LENGTH,
    PROMPT_SUMMARY_TRUNCATE_LENGTH,
    UNIQUE_ID_LENGTH,
    PROGRESS_LOG_INTERVAL_SECONDS,
    GITHUB_ENABLED,
    MAX_PROMPT_LENGTH,
    MODEL_NAME_PATTERN
)
from ..utils.logging import logger
from ..utils import (
    SessionLogCollector,
    sanitize_username,
    get_folder_tree,
    count_files_excluding_ignored,
    truncate_output,
    format_error_message,
    github_manager
)
from ..utils.async_buffer import AsyncOutputBuffer


async def update_message_with_content(
    message: discord.Message,
    content_generator: Callable[[], str],
    is_running: asyncio.Event,
    error_event: asyncio.Event
) -> None:
    """Generic message updater that only updates when content changes.
    
    Args:
        message: The Discord message to update.
        content_generator: A callable that returns the content string.
        is_running: Event that signals if the process is still running.
        error_event: Event that signals if an error has occurred.
    """
    last_content = ""
    while is_running.is_set() and not error_event.is_set():
        try:
            content = content_generator()
            if len(content) > MAX_MESSAGE_LENGTH:
                content = content[:MAX_MESSAGE_LENGTH - 3] + "```"
            
            # Only update if content has changed
            if content != last_content:
                await message.edit(content=content)
                last_content = content
        except discord.errors.HTTPException as e:
            logger.debug(f"HTTP error updating message: {e}")
        except Exception as e:
            logger.warning(f"Unexpected error updating message: {e}")
        await asyncio.sleep(UPDATE_INTERVAL)


async def update_file_tree_message(
    message: discord.Message,
    project_path: Path,
    is_running: asyncio.Event,
    error_event: asyncio.Event
) -> None:
    """Update the file tree message only when content changes."""
    def generate_tree_content() -> str:
        tree = get_folder_tree(project_path)
        return f"**📁 Project Location:** `{project_path}`\n```text\n{project_path.name}/\n{tree}\n```"
    
    await update_message_with_content(message, generate_tree_content, is_running, error_event)


async def update_output_message(
    message: discord.Message,
    output_buffer: AsyncOutputBuffer,
    is_running: asyncio.Event,
    error_event: asyncio.Event
) -> None:
    """Update the output message only when content changes."""
    async def generate_output_content() -> str:
        full_output = await output_buffer.get_content()
        truncated = truncate_output(full_output)
        content = f"**🖥️ Copilot Output:**\n```text\n{truncated if truncated else '(waiting for output...)'}\n```"
        if len(content) > MAX_MESSAGE_LENGTH:
            available = MAX_MESSAGE_LENGTH - len("**🖥️ Copilot Output:**\n```text\n\n```")
            truncated = truncate_output(full_output, available)
            content = f"**🖥️ Copilot Output:**\n```text\n{truncated}\n```"
        return content
    
    # Use a sync wrapper for the content generator pattern
    last_content = ""
    while is_running.is_set() and not error_event.is_set():
        try:
            content = await generate_output_content()
            if len(content) > MAX_MESSAGE_LENGTH:
                content = content[:MAX_MESSAGE_LENGTH - 3] + "```"
            
            if content != last_content:
                await message.edit(content=content)
                last_content = content
        except discord.errors.HTTPException as e:
            logger.debug(f"HTTP error updating output message: {e}")
        except Exception as e:
            logger.warning(f"Unexpected error updating output message: {e}")
        await asyncio.sleep(UPDATE_INTERVAL)


async def read_stream(stream, output_buffer: AsyncOutputBuffer) -> None:
    """Read from stream and append to buffer."""
    while True:
        line = await stream.readline()
        if not line:
            break
        decoded = line.decode('utf-8', errors='replace')
        await output_buffer.append(decoded)


async def _create_project_directory(
    username: str,
    session_log: SessionLogCollector
) -> Tuple[Path, str]:
    """Create and return the project directory path.
    
    Returns:
        Tuple of (project_path, folder_name)
    
    Raises:
        Exception: If directory creation fails.
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    unique_id = str(uuid.uuid4())[:UNIQUE_ID_LENGTH]
    folder_name = f"{username}_{timestamp}_{unique_id}"
    project_path = PROJECTS_DIR / folder_name
    
    project_path.mkdir(parents=True, exist_ok=True)
    session_log.info(f"Created project directory: {project_path}")
    
    return project_path, folder_name


async def _send_initial_messages(
    interaction: discord.Interaction,
    project_path: Path,
    model: Optional[str]
) -> Tuple[discord.Message, discord.Message]:
    """Send initial Discord messages and return message objects.
    
    Returns:
        Tuple of (file_tree_message, output_message)
    """
    model_info = f" (model: `{model}`)" if model else " (using default model)"
    
    file_tree_msg = await interaction.followup.send(
        f"**📁 Project Location:** `{project_path}`\n```text\n(initializing...)\n```",
        wait=True
    )
    output_msg = await interaction.channel.send(
        f"**🖥️ Copilot Output{model_info}:**\n```text\n(starting copilot...)\n```"
    )
    
    return file_tree_msg, output_msg


async def _run_copilot_process(
    project_path: Path,
    prompt: str,
    model: Optional[str],
    session_log: SessionLogCollector,
    output_buffer: AsyncOutputBuffer,
    is_running: asyncio.Event,
    error_event: asyncio.Event
) -> Tuple[bool, bool, str, Optional[asyncio.subprocess.Process]]:
    """Run the copilot process and return status.
    
    Returns:
        Tuple of (timed_out, error_occurred, error_message, process)
    """
    # Build command
    cmd = ["copilot", "-p", prompt] + COPILOT_DEFAULT_FLAGS
    if model:
        cmd.extend(["--model", model])
    
    process = None
    timed_out = False
    error_occurred = False
    error_message = ""
    
    try:
        session_log.info("Starting copilot process...")
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=str(project_path)
        )
        session_log.info(f"Copilot process started (PID: {process.pid})")
        
        # Read output with timeout
        read_task = asyncio.create_task(read_stream(process.stdout, output_buffer))
        
        # Periodic status logging
        async def log_progress():
            elapsed = 0
            while is_running.is_set():
                await asyncio.sleep(PROGRESS_LOG_INTERVAL_SECONDS)
                elapsed += PROGRESS_LOG_INTERVAL_SECONDS
                if is_running.is_set():
                    session_log.info(f"Still executing... ({elapsed}s elapsed)")
        
        progress_task = asyncio.create_task(log_progress())
        
        try:
            await asyncio.wait_for(process.wait(), timeout=TIMEOUT_SECONDS)
            session_log.info(f"Copilot process completed with exit code: {process.returncode}")
        except asyncio.TimeoutError:
            timed_out = True
            process.kill()
            await process.wait()
            await output_buffer.append("\n\n⏰ TIMEOUT: Process killed after 30 minutes.\n")
            session_log.warning("Process timed out after 30 minutes")
        
        progress_task.cancel()
        try:
            await progress_task
        except asyncio.CancelledError:
            pass
        
        # Wait for read task to complete
        read_task.cancel()
        try:
            await read_task
        except asyncio.CancelledError:
            pass
            
    except Exception as e:
        error_occurred = True
        error_message = traceback.format_exc()
        await output_buffer.append(f"\n\n❌ ERROR:\n{error_message}\n")
        error_event.set()
        session_log.error(f"Error during execution: {e}")
    
    return timed_out, error_occurred, error_message, process


async def _update_final_messages(
    file_tree_msg: discord.Message,
    output_msg: discord.Message,
    project_path: Path,
    output_buffer: AsyncOutputBuffer,
    model: Optional[str]
) -> None:
    """Update the final state of Discord messages."""
    model_info = f" (model: `{model}`)" if model else " (using default model)"
    
    try:
        tree = get_folder_tree(project_path)
        final_tree_content = f"**📁 Project Location:** `{project_path}`\n```text\n{project_path.name}/\n{tree}\n```"
        if len(final_tree_content) > MAX_MESSAGE_LENGTH:
            final_tree_content = final_tree_content[:MAX_MESSAGE_LENGTH - 3] + "```"
        await file_tree_msg.edit(content=final_tree_content)
        
        full_output = await output_buffer.get_content()
        truncated = truncate_output(full_output)
        final_output_content = f"**🖥️ Copilot Output{model_info}:**\n```text\n{truncated if truncated else '(no output)'}\n```"
        if len(final_output_content) > MAX_MESSAGE_LENGTH:
            available = MAX_MESSAGE_LENGTH - len(f"**🖥️ Copilot Output{model_info}:**\n```text\n\n```")
            truncated = truncate_output(full_output, available)
            final_output_content = f"**🖥️ Copilot Output{model_info}:**\n```text\n{truncated}\n```"
        await output_msg.edit(content=final_output_content)
    except Exception as e:
        logger.warning(f"Error updating final messages: {e}")


async def _handle_github_integration(
    project_path: Path,
    folder_name: str,
    prompt: str,
    timed_out: bool,
    error_occurred: bool,
    process: Optional[asyncio.subprocess.Process],
    session_log: SessionLogCollector
) -> str:
    """Handle GitHub integration and return status string."""
    github_url = None
    github_status = ""
    
    logger.info(f"GitHub check: enabled={GITHUB_ENABLED}, timed_out={timed_out}, error_occurred={error_occurred}, returncode={process.returncode if process else 'None'}")
    
    if GITHUB_ENABLED and not timed_out and not error_occurred and process and process.returncode == 0:
        if github_manager.is_configured():
            session_log.info("Creating GitHub repository...")
            logger.info(f"Creating GitHub repository: {folder_name}")
            repo_description = f"Created via Discord Copilot Bot: {prompt[:100]}{'...' if len(prompt) > 100 else ''}"
            
            success, message, github_url = github_manager.create_and_push_project(
                project_path=project_path,
                repo_name=folder_name,
                description=repo_description,
                private=True
            )
            
            if success:
                session_log.info(f"GitHub: {message}")
                logger.info(f"GitHub repository created successfully: {github_url}")
                github_status = f"\n**🐙 GitHub:** [View Repository]({github_url})"
            else:
                session_log.warning(f"GitHub: {message}")
                logger.warning(f"GitHub repository creation failed: {message}")
                github_status = f"\n**🐙 GitHub:** ⚠️ {message}"
        else:
            session_log.info("GitHub integration enabled but not configured")
            logger.warning("GitHub enabled but not configured (missing GITHUB_TOKEN or GITHUB_USERNAME)")
            github_status = "\n**🐙 GitHub:** Not configured (set GITHUB_TOKEN and GITHUB_USERNAME in .env)"
    elif GITHUB_ENABLED and (timed_out or error_occurred or (process and process.returncode != 0)):
        logger.info("GitHub skipped due to project creation failure")
        github_status = "\n**🐙 GitHub:** Skipped due to project creation failure"
    elif not GITHUB_ENABLED:
        logger.debug("GitHub integration is disabled")
    
    return github_status


async def _send_summary(
    interaction: discord.Interaction,
    session_log: SessionLogCollector,
    folder_name: str,
    prompt: str,
    model: Optional[str],
    timed_out: bool,
    error_occurred: bool,
    error_message: str,
    process: Optional[asyncio.subprocess.Process],
    file_count: int,
    dir_count: int,
    github_status: str
) -> None:
    """Send the final summary message with log attachment."""
    # Determine status
    if timed_out:
        status = "⏰ **TIMED OUT** - Process was killed after 30 minutes"
        status_text = "TIMED OUT"
    elif error_occurred:
        status = format_error_message("ERROR", error_message)
        status_text = "ERROR"
    elif process and process.returncode == 0:
        status = "✅ **COMPLETED SUCCESSFULLY**"
        status_text = "COMPLETED SUCCESSFULLY"
    else:
        exit_code = process.returncode if process else "unknown"
        status = f"⚠️ **COMPLETED WITH EXIT CODE {exit_code}**"
        status_text = f"COMPLETED WITH EXIT CODE {exit_code}"
    
    session_log.info(f"Completed - Files: {file_count}, Directories: {dir_count}")
    
    # Generate log markdown file
    log_markdown = session_log.get_markdown(
        prompt=prompt,
        model=model if model else 'default',
        status=status_text,
        file_count=file_count,
        dir_count=dir_count
    )
    
    summary = f"""
**📋 Project Creation Summary**

**Status:** {status}
**Prompt:**{prompt[:PROMPT_SUMMARY_TRUNCATE_LENGTH]}{'...' if len(prompt) > PROMPT_SUMMARY_TRUNCATE_LENGTH else ''}
**Model:** {model if model else 'default'}
**Files Created:** {file_count}
**Directories Created:** {dir_count}
**User:** {interaction.user.mention}{github_status}
"""
    
    try:
        log_file = discord.File(
            io.BytesIO(log_markdown.encode('utf-8')),
            filename=f"{folder_name}_log.md"
        )
        await interaction.channel.send(summary, file=log_file)
    except Exception as e:
        session_log.error(f"Failed to send summary: {e}")
        try:
            await interaction.channel.send(summary)
        except Exception:
            pass


def setup_createproject_command(bot) -> Callable:
    """Set up the /createproject command on the bot."""
    
    @bot.tree.command(name="createproject", description="Create a new project using Copilot CLI")
    @app_commands.describe(
        prompt="The prompt describing what project to create",
        model="Optional: The model to use (e.g., gpt-4, claude-3-opus)"
    )
    async def createproject(
        interaction: discord.Interaction,
        prompt: str,
        model: Optional[str] = None
    ) -> None:
        """Handle the /createproject command."""
        # Validate prompt
        prompt = prompt.strip()
        if not prompt:
            await interaction.response.send_message(
                format_error_message("Invalid Input", "Prompt cannot be empty.", include_traceback=False),
                ephemeral=True
            )
            return
        
        if len(prompt) > MAX_PROMPT_LENGTH:
            await interaction.response.send_message(
                format_error_message("Invalid Input", f"Prompt is too long (max {MAX_PROMPT_LENGTH:,} characters).", include_traceback=False),
                ephemeral=True
            )
            return
        
        # Validate model if provided
        if model and not re.match(MODEL_NAME_PATTERN, model):
            await interaction.response.send_message(
                format_error_message("Invalid Input", "Invalid model name format. Use only letters, numbers, hyphens, underscores, and dots.", include_traceback=False),
                ephemeral=True
            )
            return
        
        await interaction.response.defer()
        
        # Log GitHub configuration status
        logger.info(f"GitHub enabled: {GITHUB_ENABLED}, configured: {github_manager.is_configured()}")
        
        # Create unique project folder
        username = sanitize_username(interaction.user.name)
        
        # Initialize session log collector
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_id = str(uuid.uuid4())[:UNIQUE_ID_LENGTH]
        folder_name = f"{username}_{timestamp}_{unique_id}"
        
        session_log = SessionLogCollector(folder_name)
        session_log.info(f"User '{interaction.user.name}' started /createproject")
        session_log.info(f"Prompt: {prompt[:PROMPT_LOG_TRUNCATE_LENGTH]}{'...' if len(prompt) > PROMPT_LOG_TRUNCATE_LENGTH else ''}")
        if model:
            session_log.info(f"Model: {model}")
        
        # Create project directory
        try:
            project_path, folder_name = await _create_project_directory(username, session_log)
        except Exception as e:
            session_log.error(f"Failed to create project directory: {e}")
            await interaction.followup.send(format_error_message("Failed to create project directory", traceback.format_exc()))
            return
        
        # Send initial messages
        try:
            file_tree_msg, output_msg = await _send_initial_messages(interaction, project_path, model)
        except Exception as e:
            session_log.error(f"Failed to send Discord messages: {e}")
            await interaction.followup.send(format_error_message("Failed to send messages", traceback.format_exc()))
            return
        
        # State tracking with thread-safe buffer
        output_buffer = AsyncOutputBuffer()
        is_running = asyncio.Event()
        is_running.set()
        error_event = asyncio.Event()
        
        # Start update tasks
        tree_task = asyncio.create_task(
            update_file_tree_message(file_tree_msg, project_path, is_running, error_event)
        )
        output_task = asyncio.create_task(
            update_output_message(output_msg, output_buffer, is_running, error_event)
        )
        
        try:
            # Run the copilot process
            timed_out, error_occurred, error_message, process = await _run_copilot_process(
                project_path, prompt, model, session_log, output_buffer, is_running, error_event
            )
        finally:
            is_running.clear()
            
            # Wait for update tasks to finish
            tree_task.cancel()
            output_task.cancel()
            try:
                await tree_task
            except asyncio.CancelledError:
                pass
            try:
                await output_task
            except asyncio.CancelledError:
                pass
        
        # Final updates
        await _update_final_messages(file_tree_msg, output_msg, project_path, output_buffer, model)
        
        # Count files created (excluding ignored folders)
        file_count, dir_count = count_files_excluding_ignored(project_path)
        
        # Handle GitHub integration
        github_status = await _handle_github_integration(
            project_path, folder_name, prompt, timed_out, error_occurred, process, session_log
        )
        
        # Send summary message
        await _send_summary(
            interaction, session_log, folder_name, prompt, model,
            timed_out, error_occurred, error_message, process,
            file_count, dir_count, github_status
        )
    
    return createproject
