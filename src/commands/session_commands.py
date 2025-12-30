"""
Session-based project commands for conversational prompt building.

This module provides:
- /startproject: Begin a prompt-building session
- /buildproject: Finalize and create the project
- /cancelprompt: Cancel an active session
- Message listener for capturing user input during sessions
"""

import asyncio
import io
from typing import Optional, Callable

import discord
from discord import app_commands

from ..config import (
    MAX_PROMPT_LENGTH,
    MAX_MESSAGE_LENGTH,
    MODEL_NAME_PATTERN,
    SESSION_TIMEOUT_MINUTES,
)
from ..utils.logging import logger
from ..utils.text_utils import format_error_message, split_message
from ..utils.session_manager import get_session_manager
from ..utils.prompt_refinement import get_refinement_service
from .createproject import (
    _create_project_directory,
    _send_initial_message,
    _run_copilot_process,
    _update_final_message,
    _handle_github_integration,
    _cleanup_project_directory,
    update_unified_message,
)
from ..utils import (
    SessionLogCollector,
    sanitize_username,
    AsyncOutputBuffer,
)
from ..config import (
    PROJECTS_DIR,
    TIMEOUT_SECONDS,
    TIMEOUT_MINUTES,
    PROMPT_LOG_TRUNCATE_LENGTH,
    UNIQUE_ID_LENGTH,
    CLEANUP_AFTER_PUSH,
    get_prompt_template,
)
import re
import uuid
from datetime import datetime


def setup_session_commands(bot) -> tuple:
    """Set up the session-based project commands on the bot.
    
    Returns:
        Tuple of (startproject, buildproject, cancelprompt) command functions.
    """
    session_manager = get_session_manager(SESSION_TIMEOUT_MINUTES)
    refinement_service = get_refinement_service()
    
    @bot.tree.command(
        name="startproject",
        description="Start a conversational session to build your project prompt"
    )
    @app_commands.describe(
        description="Initial description of your project idea"
    )
    async def startproject(
        interaction: discord.Interaction,
        description: Optional[str] = None
    ) -> None:
        """Start a new prompt-building session."""
        await interaction.response.defer()
        
        user_id = interaction.user.id
        channel_id = interaction.channel.id
        
        # Check for existing session
        existing = await session_manager.get_session(user_id, channel_id)
        if existing:
            await interaction.followup.send(
                "⚠️ You already have an active session in this channel.\n"
                f"Messages collected: {existing.get_message_count()} "
                f"({existing.get_word_count():,} words)\n\n"
                "Use `/buildproject` to create your project, or `/cancelprompt` to start over.",
                ephemeral=True
            )
            return
        
        # Start new session
        session = await session_manager.start_session(user_id, channel_id)
        
        # Build initial response
        if description:
            # Add the initial description
            session.add_message(description)
            session.add_conversation_turn("user", description)
            
            # Get AI response with clarifying questions
            if refinement_service.is_configured():
                ai_response = await refinement_service.generate_initial_questions(description)
                session.add_conversation_turn("assistant", ai_response)
                
                # Build header and footer messages
                desc_preview = description[:200] + ('...' if len(description) > 200 else '')
                header_msg = (
                    f"📝 **Prompt Session Started!**\n\n"
                    f"Your description: *{desc_preview}*\n\n"
                    f"🤖 **AI Response:**"
                )
                footer_msg = (
                    f"\n\n*Continue the conversation by sending messages in this channel. "
                    f"Type `/buildproject` when ready, or `/cancelprompt` to abort.*"
                )
                
                # Send header
                bot_msg = await interaction.followup.send(header_msg)
                session.add_bot_message_id(bot_msg.id)
                
                # Split AI response and send in chunks
                ai_chunks = split_message(ai_response)
                for i, chunk in enumerate(ai_chunks):
                    # Add footer to the last chunk
                    if i == len(ai_chunks) - 1:
                        chunk_with_footer = chunk + footer_msg
                        # If adding footer exceeds limit, send separately
                        if len(chunk_with_footer) > MAX_MESSAGE_LENGTH:
                            bot_msg = await interaction.channel.send(chunk)
                            session.add_bot_message_id(bot_msg.id)
                            bot_msg = await interaction.channel.send(footer_msg.strip())
                            session.add_bot_message_id(bot_msg.id)
                        else:
                            bot_msg = await interaction.channel.send(chunk_with_footer)
                            session.add_bot_message_id(bot_msg.id)
                    else:
                        bot_msg = await interaction.channel.send(chunk)
                        session.add_bot_message_id(bot_msg.id)
            else:
                bot_msg = await interaction.followup.send(
                    f"📝 **Prompt Session Started!**\n\n"
                    f"Your description has been saved. Send more messages to add to your prompt.\n\n"
                    f"⚠️ *AI refinement not configured - messages will be collected without AI assistance.*\n\n"
                    f"Type `/buildproject` when ready, or `/cancelprompt` to abort."
                )
                session.add_bot_message_id(bot_msg.id)
        else:
            bot_msg = await interaction.followup.send(
                "📝 **Prompt Session Started!**\n\n"
                "Describe your project in this channel. I'll ask clarifying questions "
                "to help refine your requirements.\n\n"
                "You can send as many messages as you need - there's no character limit!\n\n"
                "Commands:\n"
                "• `/buildproject` - Create your project when ready\n"
                "• `/buildproject model:claude-sonnet` - Specify a model\n"
                "• `/cancelprompt` - Cancel and start over\n\n"
                f"*Session expires after {SESSION_TIMEOUT_MINUTES} minutes of inactivity.*"
            )
            session.add_bot_message_id(bot_msg.id)
        
        logger.info(f"Started prompt session for user {interaction.user.name} in channel {channel_id}")
    
    @bot.tree.command(
        name="buildproject",
        description="Finalize your prompt and create the project"
    )
    @app_commands.describe(
        model="Optional: The model to use (e.g., gpt-4, claude-3-opus)"
    )
    async def buildproject(
        interaction: discord.Interaction,
        model: Optional[str] = None
    ) -> None:
        """Finalize the session and create the project."""
        user_id = interaction.user.id
        channel_id = interaction.channel.id
        
        # Get the session
        session = await session_manager.get_session(user_id, channel_id)
        if not session:
            await interaction.response.send_message(
                "❌ No active prompt session found.\n"
                "Use `/startproject` to begin a new session.",
                ephemeral=True
            )
            return
        
        # Check if we have any content
        if session.get_message_count() == 0:
            await interaction.response.send_message(
                "❌ No messages in your session yet.\n"
                "Send some messages describing your project first!",
                ephemeral=True
            )
            return
        
        # Validate model if provided
        if model and not re.match(MODEL_NAME_PATTERN, model):
            await interaction.response.send_message(
                format_error_message(
                    "Invalid Input",
                    "Invalid model name format. Use only letters, numbers, hyphens, underscores, and dots.",
                    include_traceback=False
                ),
                ephemeral=True
            )
            return
        
        await interaction.response.defer()
        
        # Use already-refined prompt if available, otherwise finalize
        if session.refined_prompt:
            final_prompt = session.refined_prompt
            logger.info("Using pre-refined prompt from session")
        elif refinement_service.is_configured() and session.conversation_history:
            final_prompt = await refinement_service.finalize_prompt(session.conversation_history)
        else:
            final_prompt = session.get_full_user_input()
        
        # Validate prompt length
        if len(final_prompt) > MAX_PROMPT_LENGTH:
            await interaction.followup.send(
                format_error_message(
                    "Prompt Too Long",
                    f"Final prompt is {len(final_prompt):,} characters "
                    f"(max {MAX_PROMPT_LENGTH:,}).\n"
                    "Try to be more concise or split into multiple projects.",
                    include_traceback=False
                )
            )
            return
        
        # Store the refined prompt in session
        session.refined_prompt = final_prompt
        session.model = model
        
        # Collect message IDs before ending session
        message_ids_to_delete = session.message_ids.copy()
        
        # End the session
        await session_manager.end_session(user_id, channel_id)
        
        # Delete all session messages from the channel (cleanup the conversation)
        if message_ids_to_delete:
            try:
                channel = interaction.channel
                for msg_id in message_ids_to_delete:
                    try:
                        msg = await channel.fetch_message(msg_id)
                        await msg.delete()
                    except discord.NotFound:
                        pass  # Message already deleted
                    except discord.Forbidden:
                        logger.warning(f"No permission to delete message {msg_id}")
                    except Exception as e:
                        logger.warning(f"Failed to delete message {msg_id}: {e}")
            except Exception as e:
                logger.warning(f"Failed to cleanup session messages: {e}")
        
        # Acquire semaphore
        semaphore = bot.request_semaphore
        await semaphore.acquire()
        
        try:
            # Run the project creation (reusing logic from createproject.py)
            await _execute_project_creation(
                interaction=interaction,
                prompt=final_prompt,
                model=model,
                bot=bot
            )
        finally:
            semaphore.release()
        
        logger.info(f"Completed buildproject for user {interaction.user.name}")
    
    @bot.tree.command(
        name="cancelprompt",
        description="Cancel your active prompt-building session"
    )
    async def cancelprompt(interaction: discord.Interaction) -> None:
        """Cancel an active prompt session."""
        user_id = interaction.user.id
        channel_id = interaction.channel.id
        
        session = await session_manager.end_session(user_id, channel_id)
        
        if session:
            await interaction.response.send_message(
                f"🗑️ **Session Cancelled**\n\n"
                f"Discarded {session.get_message_count()} messages "
                f"({session.get_word_count():,} words).\n\n"
                f"Use `/startproject` to begin a new session."
            )
            logger.info(f"Cancelled prompt session for user {interaction.user.name}")
        else:
            await interaction.response.send_message(
                "ℹ️ No active session to cancel.",
                ephemeral=True
            )
    
    return startproject, buildproject, cancelprompt


async def _execute_project_creation(
    interaction: discord.Interaction,
    prompt: str,
    model: Optional[str],
    bot
) -> None:
    """Execute the project creation process.
    
    This is extracted to be reusable from both /createproject and /buildproject.
    """
    from ..utils import github_manager
    
    # Create unique project folder
    username = sanitize_username(interaction.user.name)
    
    # Initialize session log collector
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    unique_id = str(uuid.uuid4())[:UNIQUE_ID_LENGTH]
    folder_name = f"{username}_{timestamp}_{unique_id}"
    
    session_log = SessionLogCollector(folder_name)
    session_log.info(f"User '{interaction.user.name}' started project creation")
    session_log.info(f"Prompt: {prompt[:PROMPT_LOG_TRUNCATE_LENGTH]}{'...' if len(prompt) > PROMPT_LOG_TRUNCATE_LENGTH else ''}")
    if model:
        session_log.info(f"Model: {model}")
    
    # Build full prompt with template prepended
    prompt_template = get_prompt_template('createproject')
    if prompt_template:
        full_prompt = f"{prompt_template}\n\n{prompt}"
        session_log.info("Prompt template prepended from config.yaml")
    else:
        full_prompt = prompt
    
    # Create project directory
    try:
        project_path, folder_name = await _create_project_directory(username, session_log, prompt)
    except Exception as e:
        session_log.error(f"Failed to create project directory: {e}")
        await interaction.channel.send(
            format_error_message("Failed to create project directory", str(e))
        )
        return
    
    # Send initial unified message
    try:
        unified_msg = await _send_initial_message(interaction, project_path, prompt, model)
    except Exception as e:
        session_log.error(f"Failed to send Discord message: {e}")
        await interaction.channel.send(
            format_error_message("Failed to send message", str(e))
        )
        return
    
    # State tracking
    output_buffer = AsyncOutputBuffer()
    is_running = asyncio.Event()
    is_running.set()
    error_event = asyncio.Event()
    
    # Start unified update task
    unified_task = asyncio.create_task(
        update_unified_message(
            unified_msg, project_path, output_buffer, interaction,
            prompt, model, is_running, error_event
        )
    )
    
    try:
        # Run the copilot process
        timed_out, error_occurred, error_message, process = await _run_copilot_process(
            project_path, full_prompt, model, session_log, output_buffer, is_running, error_event
        )
    finally:
        is_running.clear()
        unified_task.cancel()
        try:
            await unified_task
        except asyncio.CancelledError:
            pass
    
    # Handle GitHub integration
    github_status, github_success, repo_description, github_url = await _handle_github_integration(
        project_path, folder_name, prompt, timed_out, error_occurred, process, session_log
    )
    
    # Final update to unified message
    await _update_final_message(
        unified_msg, project_path, output_buffer, interaction,
        prompt, model, timed_out, error_occurred, error_message,
        process, github_status,
        project_name=folder_name,
        description=repo_description,
        github_url=github_url
    )
    
    # Cleanup if configured
    if CLEANUP_AFTER_PUSH and github_success:
        _cleanup_project_directory(project_path, session_log)


def setup_message_listener(bot) -> Callable:
    """Set up the message listener for capturing session messages.
    
    Returns:
        The on_message event handler function.
    """
    session_manager = get_session_manager()
    refinement_service = get_refinement_service()
    
    @bot.event
    async def on_message(message: discord.Message) -> None:
        """Handle incoming messages for active sessions."""
        # Ignore bot messages
        if message.author.bot:
            return
        
        # Ignore DMs for now (could be enabled later)
        if not message.guild:
            return
        
        # Check if user has an active session in this channel
        session = await session_manager.get_session(
            message.author.id,
            message.channel.id
        )
        
        if not session:
            return
        
        # Ignore messages that look like commands
        if message.content.startswith('/'):
            return
        
        # Add message to session
        content = message.content.strip()
        if not content:
            return
        
        # Track the user's message ID for deletion on build
        session.add_message(content, message.id)
        session.add_conversation_turn("user", content)
        
        logger.info(
            f"Added message to session for {message.author.name}: "
            f"{len(content)} chars, {len(content.split())} words"
        )
        
        # Get AI response if configured
        if refinement_service.is_configured():
            async with message.channel.typing():
                ai_response, refined_prompt = await refinement_service.get_refinement_response(
                    session.conversation_history[:-1],  # Exclude the just-added message
                    content
                )
                
                session.add_conversation_turn("assistant", ai_response)
                
                if refined_prompt:
                    session.refined_prompt = refined_prompt
                    # Send refined prompt as markdown file attachment
                    file_content = f"# Refined Project Prompt\n\n{refined_prompt}"
                    file = discord.File(
                        io.BytesIO(file_content.encode('utf-8')),
                        filename="refined_prompt.md"
                    )
                    bot_msg = await message.reply(
                        "📋 **Refined Prompt Ready** - See attached file. Type `/buildproject` to create your project.",
                        file=file,
                        mention_author=False
                    )
                    session.add_bot_message_id(bot_msg.id)
                else:
                    # Send the AI response, splitting into multiple messages if needed
                    ai_chunks = split_message(f"🤖 {ai_response}")
                    for chunk in ai_chunks:
                        bot_msg = await message.channel.send(chunk)
                        session.add_bot_message_id(bot_msg.id)
        else:
            # Just acknowledge the message
            word_count = session.get_word_count()
            await message.add_reaction("✅")
            
            # Periodically remind about word count
            if session.get_message_count() % 5 == 0:
                bot_msg = await message.channel.send(
                    f"📊 *Session progress: {session.get_message_count()} messages, "
                    f"{word_count:,} words. Type `/buildproject` when ready.*"
                )
                session.add_bot_message_id(bot_msg.id)
    
    return on_message
