"""
Project creation service for orchestrating the Copilot project creation process.

This module consolidates duplicated project creation logic from createproject.py
and session_commands.py into a reusable service.
"""

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional, TYPE_CHECKING

import discord

if TYPE_CHECKING:
    from ..bot import CopilotBot

from ..config import (
    CLEANUP_AFTER_PUSH,
    PROMPT_LOG_TRUNCATE_LENGTH,
    UNIQUE_ID_LENGTH,
    get_prompt_template,
)
from ..utils import (
    AsyncOutputBuffer,
    SessionLogCollector,
    github_manager,
    sanitize_username,
)
from ..utils.logging import logger
from ..utils.text_utils import format_error_message


@dataclass
class ProjectBuildState:
    """Encapsulates the state of a project build process."""

    project_path: Optional[Path] = None
    folder_name: str = ""
    timed_out: bool = False
    error_occurred: bool = False
    error_message: str = ""
    process: Optional[asyncio.subprocess.Process] = None
    github_status: str = ""
    github_success: bool = False
    github_url: Optional[str] = None
    repo_description: Optional[str] = None
    output_buffer: AsyncOutputBuffer = field(default_factory=AsyncOutputBuffer)
    session_log: Optional[SessionLogCollector] = None

    @property
    def is_success(self) -> bool:
        """Check if the build completed successfully."""
        return (
            not self.timed_out
            and not self.error_occurred
            and self.process is not None
            and self.process.returncode == 0
        )


@dataclass
class ProjectConfiguration:
    """Encapsulates user inputs for project creation."""

    prompt: str
    model: Optional[str] = None
    username: str = ""
    user_display_name: str = ""
    user_mention: str = ""


class ProjectCreationService:
    """Orchestrates the project creation process.

    This service consolidates the shared logic between /createproject
    and /buildproject commands.
    """

    def __init__(self):
        """Initialize the project creation service."""
        # Import here to avoid circular imports
        from ..commands.createproject_helpers import (
            cleanup_project_directory,
            create_project_directory,
            handle_github_integration,
            run_copilot_process,
            send_initial_message,
            update_final_message,
            update_unified_message,
        )

        self._create_project_directory = create_project_directory
        self._send_initial_message = send_initial_message
        self._run_copilot_process = run_copilot_process
        self._update_unified_message = update_unified_message
        self._update_final_message = update_final_message
        self._handle_github_integration = handle_github_integration
        self._cleanup_project_directory = cleanup_project_directory

    async def create_project(
        self,
        interaction: discord.Interaction,
        config: ProjectConfiguration,
    ) -> ProjectBuildState:
        """Execute the full project creation workflow.

        Args:
            interaction: The Discord interaction.
            config: Project configuration with prompt, model, and user info.

        Returns:
            ProjectBuildState with the results of the build.
        """
        state = ProjectBuildState()

        # Initialize username from config or interaction
        username = config.username or sanitize_username(interaction.user.name)

        # Initialize session log
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_id = str(uuid.uuid4())[:UNIQUE_ID_LENGTH]
        log_folder_name = f"{username}_{timestamp}_{unique_id}"

        state.session_log = SessionLogCollector(log_folder_name)
        state.session_log.info(
            f"User '{interaction.user.name}' started project creation"
        )
        state.session_log.info(
            f"Prompt: {config.prompt[:PROMPT_LOG_TRUNCATE_LENGTH]}"
            f"{'...' if len(config.prompt) > PROMPT_LOG_TRUNCATE_LENGTH else ''}"
        )
        if config.model:
            state.session_log.info(f"Model: {config.model}")

        # Build full prompt with template
        prompt_template = get_prompt_template("createproject")
        if prompt_template:
            full_prompt = f"{prompt_template}\n\n{config.prompt}"
            state.session_log.info("Prompt template prepended from config.yaml")
        else:
            full_prompt = config.prompt

        # Create project directory
        try:
            (
                state.project_path,
                state.folder_name,
            ) = await self._create_project_directory(
                username, state.session_log, config.prompt
            )
        except Exception as e:
            state.session_log.error(f"Failed to create project directory: {e}")
            await interaction.channel.send(
                format_error_message("Failed to create project directory", str(e))
            )
            state.error_occurred = True
            state.error_message = str(e)
            return state

        # Send initial unified message
        try:
            unified_msg = await self._send_initial_message(
                interaction, state.project_path, config.prompt, config.model
            )
        except Exception as e:
            state.session_log.error(f"Failed to send Discord message: {e}")
            await interaction.channel.send(
                format_error_message("Failed to send message", str(e))
            )
            state.error_occurred = True
            state.error_message = str(e)
            return state

        # State tracking
        is_running = asyncio.Event()
        is_running.set()
        error_event = asyncio.Event()

        # Start unified update task
        unified_task = asyncio.create_task(
            self._update_unified_message(
                unified_msg,
                state.project_path,
                state.output_buffer,
                interaction,
                config.prompt,
                config.model,
                is_running,
                error_event,
            )
        )

        try:
            # Run the copilot process
            (
                state.timed_out,
                state.error_occurred,
                state.error_message,
                state.process,
            ) = await self._run_copilot_process(
                state.project_path,
                full_prompt,
                config.model,
                state.session_log,
                state.output_buffer,
                is_running,
                error_event,
            )
        finally:
            is_running.clear()
            unified_task.cancel()
            try:
                await unified_task
            except asyncio.CancelledError:
                pass

        # Handle GitHub integration
        (
            state.github_status,
            state.github_success,
            state.repo_description,
            state.github_url,
        ) = await self._handle_github_integration(
            state.project_path,
            state.folder_name,
            config.prompt,
            state.timed_out,
            state.error_occurred,
            state.process,
            state.session_log,
        )

        # Final update to unified message
        await self._update_final_message(
            unified_msg,
            state.project_path,
            state.output_buffer,
            interaction,
            config.prompt,
            config.model,
            state.timed_out,
            state.error_occurred,
            state.error_message,
            state.process,
            state.github_status,
            project_name=state.folder_name,
            description=state.repo_description,
            github_url=state.github_url,
        )

        # Cleanup if configured and successful
        if CLEANUP_AFTER_PUSH and state.github_success:
            self._cleanup_project_directory(state.project_path, state.session_log)

        return state


# Singleton instance
_project_creation_service: Optional[ProjectCreationService] = None


def get_project_creation_service() -> ProjectCreationService:
    """Get the singleton project creation service instance."""
    global _project_creation_service
    if _project_creation_service is None:
        _project_creation_service = ProjectCreationService()
    return _project_creation_service


def reset_project_creation_service() -> None:
    """Reset the project creation service (useful for testing)."""
    global _project_creation_service
    _project_creation_service = None
