"""
Create project command for the Discord Copilot Bot.
"""

import asyncio
import io
import traceback
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

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
    PROGRESS_LOG_INTERVAL_SECONDS
)
from ..utils.logging import logger
from ..utils import (
    SessionLogCollector,
    sanitize_username,
    get_folder_tree,
    count_files_excluding_ignored,
    truncate_output
)


async def update_file_tree_message(
    message: discord.Message,
    project_path: Path,
    is_running: asyncio.Event,
    error_event: asyncio.Event
):
    """Update the file tree message only when content changes."""
    last_content = ""
    while is_running.is_set() and not error_event.is_set():
        try:
            tree = get_folder_tree(project_path)
            content = f"**📁 Project Location:** `{project_path}`\n```text\n{project_path.name}/\n{tree}\n```"
            if len(content) > MAX_MESSAGE_LENGTH:
                content = content[:MAX_MESSAGE_LENGTH - 3] + "```"
            
            # Only update if content has changed
            if content != last_content:
                await message.edit(content=content)
                last_content = content
        except discord.errors.HTTPException as e:
            logger.debug(f"HTTP error updating file tree message: {e}")
        except Exception as e:
            logger.warning(f"Unexpected error updating file tree message: {e}")
        await asyncio.sleep(UPDATE_INTERVAL)


async def update_output_message(
    message: discord.Message,
    output_buffer: list,
    is_running: asyncio.Event,
    error_event: asyncio.Event
):
    """Update the output message only when content changes."""
    last_content = ""
    while is_running.is_set() and not error_event.is_set():
        try:
            full_output = ''.join(output_buffer)
            truncated = truncate_output(full_output)
            content = f"**🖥️ Copilot Output:**\n```text\n{truncated if truncated else '(waiting for output...)'}\n```"
            if len(content) > MAX_MESSAGE_LENGTH:
                available = MAX_MESSAGE_LENGTH - len("**🖥️ Copilot Output:**\n```text\n\n```")
                truncated = truncate_output(full_output, available)
                content = f"**🖥️ Copilot Output:**\n```text\n{truncated}\n```"
            
            # Only update if content has changed
            if content != last_content:
                await message.edit(content=content)
                last_content = content
        except discord.errors.HTTPException as e:
            logger.debug(f"HTTP error updating output message: {e}")
        except Exception as e:
            logger.warning(f"Unexpected error updating output message: {e}")
        await asyncio.sleep(UPDATE_INTERVAL)


async def read_stream(stream, output_buffer: list):
    """Read from stream and append to buffer."""
    while True:
        line = await stream.readline()
        if not line:
            break
        decoded = line.decode('utf-8', errors='replace')
        output_buffer.append(decoded)


def setup_createproject_command(bot):
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
    ):
        """Handle the /createproject command."""
        await interaction.response.defer()
        
        # Create unique project folder
        username = sanitize_username(interaction.user.name)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_id = str(uuid.uuid4())[:UNIQUE_ID_LENGTH]
        folder_name = f"{username}_{timestamp}_{unique_id}"
        project_path = PROJECTS_DIR / folder_name
        
        # Initialize session log collector
        session_log = SessionLogCollector(folder_name)
        session_log.info(f"User '{interaction.user.name}' started /createproject")
        session_log.info(f"Prompt: {prompt[:PROMPT_LOG_TRUNCATE_LENGTH]}{'...' if len(prompt) > PROMPT_LOG_TRUNCATE_LENGTH else ''}")
        if model:
            session_log.info(f"Model: {model}")
        
        try:
            project_path.mkdir(parents=True, exist_ok=True)
            session_log.info(f"Created project directory: {project_path}")
        except Exception as e:
            session_log.error(f"Failed to create project directory: {e}")
            await interaction.followup.send(f"❌ Failed to create project directory:\n```\n{traceback.format_exc()}\n```")
            return
        
        # Build command
        cmd = ["copilot", "-p", prompt] + COPILOT_DEFAULT_FLAGS
        if model:
            cmd.extend(["--model", model])
        
        # Send initial messages
        model_info = f" (model: `{model}`)" if model else " (using default model)"
        
        try:
            file_tree_msg = await interaction.followup.send(
                f"**📁 Project Location:** `{project_path}`\n```text\n(initializing...)\n```",
                wait=True
            )
            output_msg = await interaction.channel.send(
                f"**🖥️ Copilot Output{model_info}:**\n```text\n(starting copilot...)\n```"
            )
        except Exception as e:
            session_log.error(f"Failed to send Discord messages: {e}")
            await interaction.followup.send(f"❌ Failed to send messages:\n```\n{traceback.format_exc()}\n```")
            return
        
        # State tracking
        output_buffer = []
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
        
        process = None
        timed_out = False
        error_occurred = False
        error_message = ""
        
        try:
            # Start the copilot process
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
                output_buffer.append("\n\n⏰ TIMEOUT: Process killed after 30 minutes.\n")
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
            output_buffer.append(f"\n\n❌ ERROR:\n{error_message}\n")
            error_event.set()
            session_log.error(f"Error during execution: {e}")
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
        try:
            tree = get_folder_tree(project_path)
            final_tree_content = f"**📁 Project Location:** `{project_path}`\n```text\n{project_path.name}/\n{tree}\n```"
            if len(final_tree_content) > MAX_MESSAGE_LENGTH:
                final_tree_content = final_tree_content[:MAX_MESSAGE_LENGTH - 3] + "```"
            await file_tree_msg.edit(content=final_tree_content)
            
            full_output = ''.join(output_buffer)
            truncated = truncate_output(full_output)
            final_output_content = f"**🖥️ Copilot Output{model_info}:**\n```text\n{truncated if truncated else '(no output)'}\n```"
            if len(final_output_content) > MAX_MESSAGE_LENGTH:
                available = MAX_MESSAGE_LENGTH - len(f"**🖥️ Copilot Output{model_info}:**\n```text\n\n```")
                truncated = truncate_output(full_output, available)
                final_output_content = f"**🖥️ Copilot Output{model_info}:**\n```text\n{truncated}\n```"
            await output_msg.edit(content=final_output_content)
        except Exception as e:
            logger.warning(f"Error updating final messages: {e}")
        
        # Send summary message
        if timed_out:
            status = "⏰ **TIMED OUT** - Process was killed after 30 minutes"
        elif error_occurred:
            status = f"❌ **ERROR**\n```\n{error_message}\n```"
        elif process and process.returncode == 0:
            status = "✅ **COMPLETED SUCCESSFULLY**"
        else:
            exit_code = process.returncode if process else "unknown"
            status = f"⚠️ **COMPLETED WITH EXIT CODE {exit_code}**"
        
        # Count files created (excluding ignored folders)
        file_count, dir_count = count_files_excluding_ignored(project_path)
        
        session_log.info(f"Completed - Files: {file_count}, Directories: {dir_count}")
        
        # Determine status text for log
        if timed_out:
            status_text = "TIMED OUT"
        elif error_occurred:
            status_text = "ERROR"
        elif process and process.returncode == 0:
            status_text = "COMPLETED SUCCESSFULLY"
        else:
            status_text = f"COMPLETED WITH EXIT CODE {process.returncode if process else 'unknown'}"
        
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
**Project Path:** `{project_path}`
**Prompt:** {prompt[:PROMPT_SUMMARY_TRUNCATE_LENGTH]}{'...' if len(prompt) > PROMPT_SUMMARY_TRUNCATE_LENGTH else ''}
**Model:** {model if model else 'default'}
**Files Created:** {file_count}
**Directories Created:** {dir_count}
**User:** {interaction.user.mention}
"""
        
        try:
            # Create log file as Discord attachment
            log_file = discord.File(
                io.BytesIO(log_markdown.encode('utf-8')),
                filename=f"{folder_name}_log.md"
            )
            await interaction.channel.send(summary, file=log_file)
        except Exception as e:
            session_log.error(f"Failed to send summary: {e}")
            # Try sending without attachment as fallback
            try:
                await interaction.channel.send(summary)
            except Exception:
                pass
    
    return createproject
