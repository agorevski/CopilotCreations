"""
Message templates for Discord messages.

This module provides centralized message templates to improve maintainability
and enable potential localization in the future.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class ProjectSummary:
    """Data class for project summary information."""
    status: str
    prompt: str
    model: str
    file_count: int
    dir_count: int
    user_mention: str
    github_status: str = ""
    project_name: Optional[str] = None
    description: Optional[str] = None
    github_url: Optional[str] = None


class MessageTemplates:
    """Centralized message templates for Discord messages."""
    
    # Session messages
    SESSION_STARTED_WITH_DESC = (
        "📝 **Prompt Session Started!**\n\n"
        "Your description: *{desc_preview}*\n\n"
        "🤖 **AI Response:**"
    )
    
    SESSION_STARTED_NO_AI = (
        "📝 **Prompt Session Started!**\n\n"
        "Your description has been saved. Send more messages to add to your prompt.\n\n"
        "⚠️ *AI refinement not configured - messages will be collected without AI assistance.*\n\n"
        "Type `/buildproject` when ready, or `/cancelprompt` to abort."
    )
    
    SESSION_STARTED_EMPTY = (
        "📝 **Prompt Session Started!**\n\n"
        "Describe your project in this channel. I'll ask clarifying questions "
        "to help refine your requirements.\n\n"
        "You can send as many messages as you need - there's no character limit!\n\n"
        "Commands:\n"
        "• `/buildproject` - Create your project when ready\n"
        "• `/buildproject model:claude-sonnet` - Specify a model\n"
        "• `/cancelprompt` - Cancel and start over\n\n"
        "*Session expires after {timeout_minutes} minutes of inactivity.*"
    )
    
    SESSION_FOOTER = (
        "\n\n*Continue the conversation by sending messages in this channel. "
        "Type `/buildproject` when ready, or `/cancelprompt` to abort.*"
    )
    
    SESSION_EXISTS_WARNING = (
        "⚠️ You already have an active session in this channel.\n"
        "Messages collected: {message_count} ({word_count:,} words)\n\n"
        "Use `/buildproject` to create your project, or `/cancelprompt` to start over."
    )
    
    SESSION_CANCELLED = (
        "🗑️ **Session Cancelled**\n\n"
        "Discarded {message_count} messages ({word_count:,} words).\n\n"
        "Use `/startproject` to begin a new session."
    )
    
    NO_SESSION = "ℹ️ No active session to cancel."
    
    NO_ACTIVE_SESSION = (
        "❌ No active prompt session found.\n"
        "Use `/startproject` to begin a new session."
    )
    
    NO_MESSAGES_IN_SESSION = (
        "❌ No messages in your session yet.\n"
        "Send some messages describing your project first!"
    )
    
    # Progress messages
    PROGRESS_UPDATE = (
        "📊 *Session progress: {message_count} messages, "
        "{word_count:,} words. Type `/buildproject` when ready.*"
    )
    
    REFINED_PROMPT_READY = (
        "📋 **Refined Prompt Ready** - See attached file. "
        "Type `/buildproject` to create your project."
    )
    
    # Project creation messages
    PROJECT_SUCCESS = (
        "**Status:** ✅ COMPLETED SUCCESSFULLY\n"
        "**Project Name:** {project_name}\n"
        "**Description:** {description}\n"
        "**Model:** {model}\n"
        "**Files:** {file_count} | **Dirs:** {dir_count}\n"
        "**User:** {user_mention}{github_link}"
    )
    
    PROJECT_IN_PROGRESS = "🔄 **IN PROGRESS**"
    PROJECT_TIMED_OUT = "⏰ **TIMED OUT** - Process was killed after {timeout_minutes} minutes"
    PROJECT_COMPLETED = "✅ **COMPLETED SUCCESSFULLY**"
    PROJECT_COMPLETED_WITH_CODE = "⚠️ **COMPLETED WITH EXIT CODE {exit_code}**"
    
    SUMMARY_TEMPLATE = (
        "📋 Summary\n"
        "Status: {status}\n"
        "Prompt: {truncated_prompt}\n"
        "Model: {model}\n"
        "Files: {file_count} | Dirs: {dir_count}\n"
        "User: {user_mention}{github_status}"
    )
    
    @classmethod
    def format_session_started_with_desc(cls, desc_preview: str) -> str:
        """Format the session started message with description."""
        return cls.SESSION_STARTED_WITH_DESC.format(desc_preview=desc_preview)
    
    @classmethod
    def format_session_started_empty(cls, timeout_minutes: int) -> str:
        """Format the session started message without description."""
        return cls.SESSION_STARTED_EMPTY.format(timeout_minutes=timeout_minutes)
    
    @classmethod
    def format_session_exists_warning(cls, message_count: int, word_count: int) -> str:
        """Format the existing session warning."""
        return cls.SESSION_EXISTS_WARNING.format(
            message_count=message_count,
            word_count=word_count
        )
    
    @classmethod
    def format_session_cancelled(cls, message_count: int, word_count: int) -> str:
        """Format the session cancelled message."""
        return cls.SESSION_CANCELLED.format(
            message_count=message_count,
            word_count=word_count
        )
    
    @classmethod
    def format_progress_update(cls, message_count: int, word_count: int) -> str:
        """Format the progress update message."""
        return cls.PROGRESS_UPDATE.format(
            message_count=message_count,
            word_count=word_count
        )
    
    @classmethod
    def format_project_success(cls, summary: ProjectSummary) -> str:
        """Format the successful project completion message."""
        github_link = ""
        if summary.github_url:
            github_link = f"\n**🐙 GitHub:** [View Repository]({summary.github_url})"
        elif summary.github_status:
            github_link = summary.github_status
        
        return cls.PROJECT_SUCCESS.format(
            project_name=summary.project_name or "(unnamed)",
            description=summary.description or "(No description generated)",
            model=summary.model,
            file_count=summary.file_count,
            dir_count=summary.dir_count,
            user_mention=summary.user_mention,
            github_link=github_link
        )
    
    @classmethod
    def format_summary(
        cls,
        status: str,
        truncated_prompt: str,
        model: str,
        file_count: int,
        dir_count: int,
        user_mention: str,
        github_status: str = ""
    ) -> str:
        """Format the project summary section."""
        return cls.SUMMARY_TEMPLATE.format(
            status=status,
            truncated_prompt=truncated_prompt,
            model=model,
            file_count=file_count,
            dir_count=dir_count,
            user_mention=user_mention,
            github_status=github_status
        )
