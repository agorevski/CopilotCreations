"""
Create project command for the Discord Copilot Bot.
"""

import asyncio
import io
import os
import re
import shutil
import stat
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
    TIMEOUT_MINUTES,
    UPDATE_INTERVAL,
    MAX_MESSAGE_LENGTH,
    MAX_FOLDER_STRUCTURE_LENGTH,
    MAX_COPILOT_OUTPUT_LENGTH,
    MAX_SUMMARY_LENGTH,
    COPILOT_DEFAULT_FLAGS,
    PROMPT_LOG_TRUNCATE_LENGTH,
    PROMPT_SUMMARY_TRUNCATE_LENGTH,
    UNIQUE_ID_LENGTH,
    PROGRESS_LOG_INTERVAL_SECONDS,
    GITHUB_ENABLED,
    GITHUB_REPO_PRIVATE,
    CLEANUP_AFTER_PUSH,
    MAX_PROMPT_LENGTH,
    MODEL_NAME_PATTERN,
    MAX_PARALLEL_REQUESTS,
    get_prompt_template
)
from ..utils.logging import logger
from ..utils import (
    SessionLogCollector,
    sanitize_username,
    get_folder_tree,
    count_files_excluding_ignored,
    truncate_output,
    format_error_message,
    github_manager,
    naming_generator,
    get_process_registry
)
from ..utils.async_buffer import AsyncOutputBuffer


def _generate_folder_structure_section(project_path: Path) -> str:
    """Generate the folder structure section of the unified message.
    
    Returns:
        Folder structure string, truncated to MAX_FOLDER_STRUCTURE_LENGTH with ellipsis.
    """
    tree = get_folder_tree(project_path)
    folder_content = f"📁 {project_path.name}/\n{tree}"
    
    if len(folder_content) > MAX_FOLDER_STRUCTURE_LENGTH:
        folder_content = folder_content[:MAX_FOLDER_STRUCTURE_LENGTH - 3] + "..."
    
    return folder_content


async def _generate_copilot_output_section(output_buffer: AsyncOutputBuffer) -> str:
    """Generate the copilot output section of the unified message.
    
    Returns:
        Copilot output string, truncated to MAX_COPILOT_OUTPUT_LENGTH.
    """
    full_output = await output_buffer.get_content()
    if not full_output:
        return "(waiting for output...)"
    
    if len(full_output) > MAX_COPILOT_OUTPUT_LENGTH:
        return "..." + full_output[-(MAX_COPILOT_OUTPUT_LENGTH - 3):]
    
    return full_output


def _generate_summary_section(
    interaction: discord.Interaction,
    prompt: str,
    model: Optional[str],
    project_path: Path,
    timed_out: bool = False,
    error_occurred: bool = False,
    error_message: str = "",
    process: Optional[asyncio.subprocess.Process] = None,
    github_status: str = "",
    is_complete: bool = False
) -> str:
    """Generate the project creation summary section.
    
    Args:
        interaction: The Discord interaction.
        prompt: The user's prompt.
        model: The model name (if specified).
        project_path: Path to the project directory.
        timed_out: Whether the process timed out.
        error_occurred: Whether an error occurred.
        error_message: The error message (if any).
        process: The subprocess process object.
        github_status: GitHub integration status string.
        is_complete: Whether the process has completed.
    
    Returns:
        Summary section string.
    """
    # Determine status
    if not is_complete:
        status = "🔄 **IN PROGRESS**"
    elif timed_out:
        status = f"⏰ **TIMED OUT** - Process was killed after {TIMEOUT_MINUTES} minutes"
    elif error_occurred:
        status = format_error_message("ERROR", error_message[:100] if error_message else "Unknown error")
    elif process and process.returncode == 0:
        status = "✅ **COMPLETED SUCCESSFULLY**"
    else:
        exit_code = process.returncode if process else "unknown"
        status = f"⚠️ **COMPLETED WITH EXIT CODE {exit_code}**"
    
    # Get file/directory counts
    file_count, dir_count = count_files_excluding_ignored(project_path)
    
    # Truncate prompt for display
    truncated_prompt = prompt[:PROMPT_SUMMARY_TRUNCATE_LENGTH]
    if len(prompt) > PROMPT_SUMMARY_TRUNCATE_LENGTH:
        truncated_prompt += "..."
    
    summary = f"""📋 Summary
Status: {status}
Prompt: {truncated_prompt}
Model: {model if model else 'default'}
Files: {file_count} | Dirs: {dir_count}
User: {interaction.user.mention}{github_status}"""
    
    return summary


def _build_unified_message(
    folder_section: str,
    output_section: str,
    summary_section: str
) -> str:
    """Build the unified message from all three sections.
    
    Format:
    <Folder Structure>
    <Copilot Output>
    <Summary>
    
    Ensures each section is truncated to fit within Discord's 2000 char limit.
    """
    # Truncate each section to its max length
    if len(folder_section) > MAX_FOLDER_STRUCTURE_LENGTH:
        folder_section = folder_section[:MAX_FOLDER_STRUCTURE_LENGTH - 3] + "..."
    if len(output_section) > MAX_COPILOT_OUTPUT_LENGTH:
        output_section = "..." + output_section[-(MAX_COPILOT_OUTPUT_LENGTH - 3):]
    if len(summary_section) > MAX_SUMMARY_LENGTH:
        summary_section = summary_section[:MAX_SUMMARY_LENGTH - 3] + "..."
    
    # Build message with code blocks
    message = f"```\n{folder_section}\n```\n```\n{output_section}\n```\n{summary_section}"
    
    # Final safety truncation
    if len(message) > MAX_MESSAGE_LENGTH:
        # Preserve the summary by truncating output further
        overflow = len(message) - MAX_MESSAGE_LENGTH + 10
        if len(output_section) > overflow:
            output_section = "..." + output_section[-(len(output_section) - overflow):]
        message = f"```\n{folder_section}\n```\n```\n{output_section}\n```\n{summary_section}"
    
    return message


async def update_unified_message(
    message: discord.Message,
    project_path: Path,
    output_buffer: AsyncOutputBuffer,
    interaction: discord.Interaction,
    prompt: str,
    model: Optional[str],
    is_running: asyncio.Event,
    error_event: asyncio.Event
) -> None:
    """Update the unified message combining folder structure, output, and summary.
    
    Polls every 3 seconds to update all three sections in a single message.
    """
    last_content = ""
    current_message = message
    
    while is_running.is_set() and not error_event.is_set():
        try:
            # Generate all three sections
            folder_section = _generate_folder_structure_section(project_path)
            output_section = await _generate_copilot_output_section(output_buffer)
            summary_section = _generate_summary_section(
                interaction=interaction,
                prompt=prompt,
                model=model,
                project_path=project_path,
                is_complete=False
            )
            
            # Build unified message (truncation handled inside)
            content = _build_unified_message(folder_section, output_section, summary_section)
            
            # Only update if content has changed
            if content != last_content:
                try:
                    await current_message.edit(content=content)
                except discord.errors.HTTPException as e:
                    # Discord interaction tokens expire after 15 minutes
                    # Re-fetch the message using channel and ID to bypass the expired token
                    from ..utils.github import DISCORD_INVALID_WEBHOOK_TOKEN
                    if e.code == DISCORD_INVALID_WEBHOOK_TOKEN:
                        logger.info("Interaction token expired during updates, re-fetching message")
                        channel = interaction.channel
                        current_message = await channel.fetch_message(message.id)
                        await current_message.edit(content=content)
                    else:
                        raise
                last_content = content
                
        except discord.errors.HTTPException as e:
            logger.debug(f"HTTP error updating unified message: {e}")
        except Exception as e:
            logger.warning(f"Unexpected error updating unified message: {e}")
        
        await asyncio.sleep(UPDATE_INTERVAL)


async def read_stream(stream, output_buffer: AsyncOutputBuffer) -> None:
    """Read from stream and append to buffer, also logging to console."""
    while True:
        line = await stream.readline()
        if not line:
            break
        decoded = line.decode('utf-8', errors='replace')
        # Log copilot output to console (strip trailing newline for cleaner logs)
        logger.info(f"[copilot] {decoded.rstrip()}")
        await output_buffer.append(decoded)


async def create_project_directory(
    username: str,
    session_log: SessionLogCollector,
    prompt: str = ""
) -> Tuple[Path, str]:
    """Create and return the project directory path.
    
    Uses Azure OpenAI to generate a creative repository name if configured,
    otherwise falls back to the standard username_timestamp_uuid format.
    
    Args:
        username: Sanitized username for fallback naming.
        session_log: Session log collector.
        prompt: Project description used to generate creative names.
    
    Returns:
        Tuple of (project_path, folder_name)
    
    Raises:
        Exception: If directory creation fails.
    """
    # Try to generate a creative name using Azure OpenAI
    creative_name = None
    if naming_generator.is_configured() and prompt:
        creative_name = naming_generator.generate_name(prompt)
        if creative_name:
            session_log.info(f"Generated creative repository name: {creative_name}")
    
    # Use creative name as-is, or fallback to standard format with timestamp/uuid
    if creative_name:
        folder_name = creative_name
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_id = str(uuid.uuid4())[:UNIQUE_ID_LENGTH]
        folder_name = f"{username}_{timestamp}_{unique_id}"
        if naming_generator.is_configured():
            session_log.info("Falling back to standard naming format")
    
    project_path = PROJECTS_DIR / folder_name
    
    project_path.mkdir(parents=True, exist_ok=True)
    session_log.info(f"Created project directory: {project_path}")
    
    # Create COPILOT-PROMPT.md with the original prompt for historical purposes
    prompt_file = project_path / "COPILOT-PROMPT.md"
    prompt_content = f"""# Copilot Prompt

This file contains the original prompt given to GitHub Copilot to create this project.

## Prompt

{prompt}

---
*Generated on {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}*
"""
    prompt_file.write_text(prompt_content, encoding='utf-8')
    session_log.info(f"Created COPILOT-PROMPT.md with original prompt")
    
    return project_path, folder_name


async def send_initial_message(
    interaction: discord.Interaction,
    project_path: Path,
    prompt: str,
    model: Optional[str]
) -> discord.Message:
    """Send initial unified Discord message and return message object.
    
    Returns:
        The unified message object.
    """
    # Build initial unified message with placeholder content
    folder_section = f"📁 {project_path.name}/\n(initializing...)"
    output_section = "(starting copilot...)"
    
    model_display = model if model else 'default'
    truncated_prompt = prompt[:PROMPT_SUMMARY_TRUNCATE_LENGTH]
    if len(prompt) > PROMPT_SUMMARY_TRUNCATE_LENGTH:
        truncated_prompt += "..."
    
    summary_section = f"""📋 Summary
Status: 🔄 **IN PROGRESS**
Prompt: {truncated_prompt}
Model: {model_display}
Files: 0 | Dirs: 0
User: {interaction.user.display_name}"""
    
    content = _build_unified_message(folder_section, output_section, summary_section)
    
    unified_msg = await interaction.followup.send(content, wait=True)
    
    return unified_msg


async def run_copilot_process(
    project_path: Path,
    full_prompt: str,
    model: Optional[str],
    session_log: SessionLogCollector,
    output_buffer: AsyncOutputBuffer,
    is_running: asyncio.Event,
    error_event: asyncio.Event
) -> Tuple[bool, bool, str, Optional[asyncio.subprocess.Process]]:
    """Run the copilot process and return status.
    
    Args:
        project_path: Path to the project directory.
        full_prompt: The full prompt including any prepended templates.
        model: Optional model name.
        session_log: Session log collector.
        output_buffer: Async output buffer.
        is_running: Event that signals if the process is still running.
        error_event: Event that signals if an error has occurred.
    
    Returns:
        Tuple of (timed_out, error_occurred, error_message, process)
    """
    # Build command
    cmd = ["copilot", "-p", full_prompt] + COPILOT_DEFAULT_FLAGS
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
        
        # Register process for cleanup on shutdown
        process_registry = get_process_registry()
        await process_registry.register(process)
        
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
            await output_buffer.append(f"\n\n⏰ TIMEOUT: Process killed after {TIMEOUT_MINUTES} minutes.\n")
            session_log.warning(f"Process timed out after {TIMEOUT_MINUTES} minutes")
        finally:
            # Unregister process after completion or timeout
            await process_registry.unregister(process)
        
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


async def update_final_message(
    unified_msg: discord.Message,
    project_path: Path,
    output_buffer: AsyncOutputBuffer,
    interaction: discord.Interaction,
    prompt: str,
    model: Optional[str],
    timed_out: bool,
    error_occurred: bool,
    error_message: str,
    process: Optional[asyncio.subprocess.Process],
    github_status: str,
    project_name: Optional[str] = None,
    description: Optional[str] = None,
    github_url: Optional[str] = None
) -> None:
    """Update the final state of the unified Discord message.
    
    On successful completion, shows a clean summary without folder structure or copilot output.
    On failure/timeout, shows the full message with all sections for debugging.
    """
    try:
        # Check if project completed successfully
        is_success = (not timed_out and not error_occurred and process and process.returncode == 0)
        
        if is_success:
            # Build clean summary-only message for successful completion
            file_count, dir_count = count_files_excluding_ignored(project_path)
            
            # Use folder_name as project name if not provided
            display_name = project_name if project_name else project_path.name
            display_description = description if description else "(No description generated)"
            
            # Format GitHub link
            github_link = ""
            if github_url:
                github_link = f"\n**🐙 GitHub:** [View Repository]({github_url})"
            elif github_status:
                github_link = github_status
            
            content = f"""**Status:** ✅ COMPLETED SUCCESSFULLY
**Project Name:** {display_name}
**Description:** {display_description}
**Model:** {model if model else 'default'}
**Files:** {file_count} | **Dirs:** {dir_count}
**User:** {interaction.user.mention}{github_link}"""
        else:
            # Show full message with all sections for debugging on failure
            folder_section = _generate_folder_structure_section(project_path)
            output_section = await _generate_copilot_output_section(output_buffer)
            summary_section = _generate_summary_section(
                interaction=interaction,
                prompt=prompt,
                model=model,
                project_path=project_path,
                timed_out=timed_out,
                error_occurred=error_occurred,
                error_message=error_message,
                process=process,
                github_status=github_status,
                is_complete=True
            )
            
            # Build final unified message (truncation handled inside)
            content = _build_unified_message(folder_section, output_section, summary_section)
        
        try:
            await unified_msg.edit(content=content)
        except discord.errors.HTTPException as e:
            # Discord interaction tokens expire after 15 minutes
            # Re-fetch the message using channel and ID to bypass the expired token
            from ..utils.github import DISCORD_INVALID_WEBHOOK_TOKEN
            if e.code == DISCORD_INVALID_WEBHOOK_TOKEN:
                logger.info("Interaction token expired, re-fetching message to edit")
                channel = interaction.channel
                fresh_msg = await channel.fetch_message(unified_msg.id)
                await fresh_msg.edit(content=content)
            else:
                raise
    except Exception as e:
        logger.warning(f"Error updating final unified message: {e}")


async def handle_github_integration(
    project_path: Path,
    folder_name: str,
    prompt: str,
    timed_out: bool,
    error_occurred: bool,
    process: Optional[asyncio.subprocess.Process],
    session_log: SessionLogCollector
) -> Tuple[str, bool, Optional[str], Optional[str]]:
    """Handle GitHub integration and return status string.
    
    Returns:
        Tuple of (github_status, github_success, repo_description, github_url)
    """
    github_url = None
    github_status = ""
    repo_description = None
    
    logger.info(f"GitHub check: enabled={GITHUB_ENABLED}, timed_out={timed_out}, error_occurred={error_occurred}, returncode={process.returncode if process else 'None'}")
    
    if GITHUB_ENABLED and not timed_out and not error_occurred and process and process.returncode == 0:
        if github_manager.is_configured():
            session_log.info("Creating GitHub repository...")
            logger.info(f"Creating GitHub repository: {folder_name}")
            
            # Try to generate a description using Azure OpenAI
            if naming_generator.is_configured():
                repo_description = naming_generator.generate_description(prompt)
                if repo_description:
                    session_log.info(f"Generated repository description: {repo_description}")
            
            # Fallback to truncated prompt if generation fails
            if not repo_description:
                # Sanitize and truncate the prompt as a fallback description
                repo_description = github_manager.sanitize_description(prompt)
                session_log.info("Using sanitized prompt as repository description")
            
            success, message, github_url = github_manager.create_and_push_project(
                project_path=project_path,
                repo_name=folder_name,
                description=repo_description,
                private=GITHUB_REPO_PRIVATE
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
    
    return github_status, github_url is not None, repo_description, github_url


def _handle_remove_readonly(func, path, exc_info):
    """Error handler for shutil.rmtree to handle read-only files on Windows.
    
    Git creates read-only files in .git/objects which cause Access Denied errors.
    This handler removes the read-only attribute and retries the removal.
    """
    # Check if it's a permission error (Access Denied)
    if isinstance(exc_info[1], PermissionError):
        # Remove read-only attribute
        os.chmod(path, stat.S_IWRITE)
        # Retry the removal
        func(path)
    else:
        raise exc_info[1]


def cleanup_project_directory(
    project_path: Path,
    session_log: SessionLogCollector
) -> bool:
    """Delete the local project directory after successful GitHub push.
    
    Args:
        project_path: Path to the project directory to delete.
        session_log: Session log collector.
    
    Returns:
        True if cleanup was successful, False otherwise.
    """
    try:
        if project_path.exists():
            # Use onerror handler to deal with read-only files (e.g., .git/objects)
            shutil.rmtree(project_path, onerror=_handle_remove_readonly)
            session_log.info(f"Cleaned up local project directory: {project_path}")
            logger.info(f"Cleaned up local project directory: {project_path}")
            return True
    except Exception as e:
        session_log.warning(f"Failed to cleanup project directory: {e}")
        logger.warning(f"Failed to cleanup project directory {project_path}: {e}")
    return False


async def _send_log_file(
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
    output_buffer: AsyncOutputBuffer
) -> None:
    """Send the log file attachment after project creation completes."""
    # Determine status text for log
    if timed_out:
        status_text = "TIMED OUT"
    elif error_occurred:
        status_text = "ERROR"
    elif process and process.returncode == 0:
        status_text = "COMPLETED SUCCESSFULLY"
    else:
        exit_code = process.returncode if process else "unknown"
        status_text = f"COMPLETED WITH EXIT CODE {exit_code}"
    
    session_log.info(f"Completed - Files: {file_count}, Directories: {dir_count}")
    
    # Get the copilot output from the buffer
    copilot_output = await output_buffer.get_content()
    
    # Generate log markdown file
    log_markdown = session_log.get_markdown(
        prompt=prompt,
        model=model if model else 'default',
        status=status_text,
        file_count=file_count,
        dir_count=dir_count,
        copilot_output=copilot_output
    )
    
    try:
        log_file = discord.File(
            io.BytesIO(log_markdown.encode('utf-8')),
            filename=f"{folder_name}_log.md"
        )
        await interaction.channel.send(file=log_file)
    except Exception as e:
        session_log.error(f"Failed to send log file: {e}")


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
        
        # Acquire semaphore to limit parallel requests
        semaphore = bot.request_semaphore
        await semaphore.acquire()
        
        try:
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
            
            # Build full prompt with template prepended (user prompt is kept separate for display)
            prompt_template = get_prompt_template('createproject')
            if prompt_template:
                full_prompt = f"{prompt_template}\n\n{prompt}"
                session_log.info("Prompt template prepended from config.yaml")
            else:
                full_prompt = prompt
            
            # Create project directory (uses Azure OpenAI for creative naming if configured)
            try:
                project_path, folder_name = await create_project_directory(username, session_log, prompt)
            except Exception as e:
                session_log.error(f"Failed to create project directory: {e}")
                await interaction.followup.send(format_error_message("Failed to create project directory", traceback.format_exc()))
                return
            
            # Send initial unified message
            try:
                unified_msg = await send_initial_message(interaction, project_path, prompt, model)
            except Exception as e:
                session_log.error(f"Failed to send Discord message: {e}")
                await interaction.followup.send(format_error_message("Failed to send message", traceback.format_exc()))
                return
            
            # State tracking with thread-safe buffer
            output_buffer = AsyncOutputBuffer()
            is_running = asyncio.Event()
            is_running.set()
            error_event = asyncio.Event()
            
            # Start unified update task (single 3-second timer for all sections)
            unified_task = asyncio.create_task(
                update_unified_message(
                    unified_msg, project_path, output_buffer, interaction,
                    prompt, model, is_running, error_event
                )
            )
            
            try:
                # Run the copilot process with full prompt (includes template)
                timed_out, error_occurred, error_message, process = await run_copilot_process(
                    project_path, full_prompt, model, session_log, output_buffer, is_running, error_event
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
            github_status, github_success, repo_description, github_url = await handle_github_integration(
                project_path, folder_name, prompt, timed_out, error_occurred, process, session_log
            )
            
            # Final update to unified message with complete status
            await update_final_message(
                unified_msg, project_path, output_buffer, interaction,
                prompt, model, timed_out, error_occurred, error_message,
                process, github_status,
                project_name=folder_name,
                description=repo_description,
                github_url=github_url
            )
            
            # Count files created (excluding ignored folders)
            file_count, dir_count = count_files_excluding_ignored(project_path)
            
            # Send log file attachment
            await _send_log_file(
                interaction, session_log, folder_name, prompt, model,
                timed_out, error_occurred, error_message, process,
                file_count, dir_count, output_buffer
            )
            
            # Cleanup local project directory after successful GitHub push
            if CLEANUP_AFTER_PUSH and github_success:
                cleanup_project_directory(project_path, session_log)
        finally:
            semaphore.release()
    
    return createproject
