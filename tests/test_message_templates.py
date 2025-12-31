"""
Tests for message templates module.

This module tests the MessageTemplates class which provides formatted
message strings for Discord bot responses and ProjectSummary dataclass.
"""

import pytest

from src.utils.message_templates import MessageTemplates, ProjectSummary


class TestMessageTemplates:
    """Tests for MessageTemplates class and its formatting methods."""
    
    def test_format_methods(self):
        """
        Tests all message formatting methods:
        - Session started with description (includes AI response note)
        - Session started empty (includes timeout and buildproject hint)
        - Session exists warning (shows message/word counts)
        - Session cancelled (shows deleted message info)
        - Progress update (shows current counts)
        - Summary template (includes all project info)
        """
        # Session started with description
        started_desc = MessageTemplates.format_session_started_with_desc("Test project")
        assert "📝 **Prompt Session Started!**" in started_desc
        assert "Test project" in started_desc
        assert "AI Response" in started_desc
        
        # Session started empty
        started_empty = MessageTemplates.format_session_started_empty(30)
        assert "📝 **Prompt Session Started!**" in started_empty
        assert "30 minutes" in started_empty
        assert "/buildproject" in started_empty
        
        # Session exists warning
        exists_warn = MessageTemplates.format_session_exists_warning(5, 100)
        assert "5" in exists_warn
        assert "100" in exists_warn
        assert "/buildproject" in exists_warn
        
        # Session cancelled
        cancelled = MessageTemplates.format_session_cancelled(3, 50)
        assert "🗑️ **Session Cancelled**" in cancelled
        assert "3 messages" in cancelled
        assert "50" in cancelled
        
        # Progress update
        progress = MessageTemplates.format_progress_update(10, 500)
        assert "10 messages" in progress
        assert "500" in progress
        
        # Summary template with all fields
        summary = MessageTemplates.format_summary(
            status="✅ COMPLETED",
            truncated_prompt="Test prompt...",
            model="gpt-4",
            file_count=10,
            dir_count=3,
            user_mention="@user",
            github_status="\n**🐙 GitHub:** Success"
        )
        assert "✅ COMPLETED" in summary
        assert "Test prompt..." in summary
        assert "gpt-4" in summary
        assert "10" in summary
        assert "3" in summary
        assert "@user" in summary
        assert "GitHub" in summary


class TestProjectSummary:
    """Tests for ProjectSummary dataclass and format_project_success method."""
    
    def test_dataclass_and_formatting(self):
        """
        Tests ProjectSummary creation and formatting:
        - Basic creation with required fields
        - Default github_status is empty
        - Creation with GitHub info
        - format_project_success with GitHub URL
        - format_project_success without GitHub URL
        - format_project_success with github_status fallback
        """
        # Basic creation
        summary = ProjectSummary(
            status="completed",
            prompt="Test prompt",
            model="gpt-4",
            file_count=5,
            dir_count=2,
            user_mention="@user"
        )
        assert summary.status == "completed"
        assert summary.prompt == "Test prompt"
        assert summary.model == "gpt-4"
        assert summary.file_count == 5
        assert summary.dir_count == 2
        assert summary.user_mention == "@user"
        assert summary.github_status == ""  # Default
        
        # With GitHub info
        summary_gh = ProjectSummary(
            status="completed",
            prompt="Test prompt",
            model="gpt-4",
            file_count=5,
            dir_count=2,
            user_mention="@user",
            github_url="https://github.com/user/repo",
            project_name="test-project",
            description="A test project"
        )
        assert summary_gh.github_url == "https://github.com/user/repo"
        assert summary_gh.project_name == "test-project"
        assert summary_gh.description == "A test project"
        
        # format_project_success with GitHub URL
        result_with_gh = MessageTemplates.format_project_success(ProjectSummary(
            status="completed",
            prompt="Test prompt",
            model="gpt-4",
            file_count=10,
            dir_count=3,
            user_mention="@user",
            project_name="my-project",
            description="My project description",
            github_url="https://github.com/user/my-project"
        ))
        assert "✅ COMPLETED SUCCESSFULLY" in result_with_gh
        assert "my-project" in result_with_gh
        assert "My project description" in result_with_gh
        assert "gpt-4" in result_with_gh
        assert "10" in result_with_gh
        assert "github.com/user/my-project" in result_with_gh
        
        # format_project_success without GitHub URL
        result_no_gh = MessageTemplates.format_project_success(ProjectSummary(
            status="completed",
            prompt="Test prompt",
            model="default",
            file_count=5,
            dir_count=1,
            user_mention="@user",
            project_name="local-project"
        ))
        assert "local-project" in result_no_gh
        assert "No description generated" in result_no_gh
        
        # format_project_success with github_status fallback
        result_fallback = MessageTemplates.format_project_success(ProjectSummary(
            status="completed",
            prompt="Test prompt",
            model="default",
            file_count=5,
            dir_count=1,
            user_mention="@user",
            github_status="\n**🐙 GitHub:** ⚠️ Failed"
        ))
        assert "⚠️ Failed" in result_fallback


class TestMessageTemplateConstants:
    """Tests for message template constants availability."""
    
    def test_all_templates_defined(self):
        """
        Verifies all required message templates are defined:
        - Session messages (started, exists, cancelled, no session)
        - Project messages (success, in progress, timed out, completed)
        """
        # Session messages
        assert MessageTemplates.SESSION_STARTED_WITH_DESC
        assert MessageTemplates.SESSION_STARTED_NO_AI
        assert MessageTemplates.SESSION_STARTED_EMPTY
        assert MessageTemplates.SESSION_FOOTER
        assert MessageTemplates.SESSION_EXISTS_WARNING
        assert MessageTemplates.SESSION_CANCELLED
        assert MessageTemplates.NO_SESSION
        assert MessageTemplates.NO_ACTIVE_SESSION
        assert MessageTemplates.NO_MESSAGES_IN_SESSION
        
        # Project messages
        assert MessageTemplates.PROJECT_SUCCESS
        assert MessageTemplates.PROJECT_IN_PROGRESS
        assert MessageTemplates.PROJECT_TIMED_OUT
        assert MessageTemplates.PROJECT_COMPLETED
        assert MessageTemplates.PROJECT_COMPLETED_WITH_CODE
        assert MessageTemplates.SUMMARY_TEMPLATE
