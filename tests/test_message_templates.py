"""
Tests for message templates module.
"""

import pytest

from src.utils.message_templates import MessageTemplates, ProjectSummary


class TestMessageTemplates:
    """Tests for MessageTemplates class."""
    
    def test_session_started_with_desc_format(self):
        """Test formatting session started with description."""
        result = MessageTemplates.format_session_started_with_desc("Test project")
        
        assert "📝 **Prompt Session Started!**" in result
        assert "Test project" in result
        assert "AI Response" in result
    
    def test_session_started_empty_format(self):
        """Test formatting session started without description."""
        result = MessageTemplates.format_session_started_empty(30)
        
        assert "📝 **Prompt Session Started!**" in result
        assert "30 minutes" in result
        assert "/buildproject" in result
    
    def test_session_exists_warning_format(self):
        """Test formatting existing session warning."""
        result = MessageTemplates.format_session_exists_warning(5, 100)
        
        assert "5" in result
        assert "100" in result
        assert "/buildproject" in result
    
    def test_session_cancelled_format(self):
        """Test formatting session cancelled message."""
        result = MessageTemplates.format_session_cancelled(3, 50)
        
        assert "🗑️ **Session Cancelled**" in result
        assert "3 messages" in result
        assert "50" in result
    
    def test_progress_update_format(self):
        """Test formatting progress update."""
        result = MessageTemplates.format_progress_update(10, 500)
        
        assert "10 messages" in result
        assert "500" in result
    
    def test_format_summary(self):
        """Test formatting project summary."""
        result = MessageTemplates.format_summary(
            status="✅ COMPLETED",
            truncated_prompt="Test prompt...",
            model="gpt-4",
            file_count=10,
            dir_count=3,
            user_mention="@user",
            github_status="\n**🐙 GitHub:** Success"
        )
        
        assert "✅ COMPLETED" in result
        assert "Test prompt..." in result
        assert "gpt-4" in result
        assert "10" in result
        assert "3" in result
        assert "@user" in result
        assert "GitHub" in result


class TestProjectSummary:
    """Tests for ProjectSummary dataclass."""
    
    def test_project_summary_creation(self):
        """Test creating a ProjectSummary."""
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
    
    def test_project_summary_with_github(self):
        """Test ProjectSummary with GitHub info."""
        summary = ProjectSummary(
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
        
        assert summary.github_url == "https://github.com/user/repo"
        assert summary.project_name == "test-project"
        assert summary.description == "A test project"


class TestFormatProjectSuccess:
    """Tests for format_project_success method."""
    
    def test_format_with_github_url(self):
        """Test formatting success message with GitHub URL."""
        summary = ProjectSummary(
            status="completed",
            prompt="Test prompt",
            model="gpt-4",
            file_count=10,
            dir_count=3,
            user_mention="@user",
            project_name="my-project",
            description="My project description",
            github_url="https://github.com/user/my-project"
        )
        
        result = MessageTemplates.format_project_success(summary)
        
        assert "✅ COMPLETED SUCCESSFULLY" in result
        assert "my-project" in result
        assert "My project description" in result
        assert "gpt-4" in result
        assert "10" in result
        assert "3" in result
        assert "github.com/user/my-project" in result
    
    def test_format_without_github_url(self):
        """Test formatting success message without GitHub URL."""
        summary = ProjectSummary(
            status="completed",
            prompt="Test prompt",
            model="default",
            file_count=5,
            dir_count=1,
            user_mention="@user",
            project_name="local-project"
        )
        
        result = MessageTemplates.format_project_success(summary)
        
        assert "local-project" in result
        assert "No description generated" in result
    
    def test_format_with_github_status_fallback(self):
        """Test that github_status is used when github_url is None."""
        summary = ProjectSummary(
            status="completed",
            prompt="Test prompt",
            model="default",
            file_count=5,
            dir_count=1,
            user_mention="@user",
            github_status="\n**🐙 GitHub:** ⚠️ Failed"
        )
        
        result = MessageTemplates.format_project_success(summary)
        
        assert "⚠️ Failed" in result


class TestMessageTemplateConstants:
    """Tests for message template constants."""
    
    def test_session_messages_defined(self):
        """Test that session messages are defined."""
        assert MessageTemplates.SESSION_STARTED_WITH_DESC
        assert MessageTemplates.SESSION_STARTED_NO_AI
        assert MessageTemplates.SESSION_STARTED_EMPTY
        assert MessageTemplates.SESSION_FOOTER
        assert MessageTemplates.SESSION_EXISTS_WARNING
        assert MessageTemplates.SESSION_CANCELLED
        assert MessageTemplates.NO_SESSION
        assert MessageTemplates.NO_ACTIVE_SESSION
        assert MessageTemplates.NO_MESSAGES_IN_SESSION
    
    def test_project_messages_defined(self):
        """Test that project messages are defined."""
        assert MessageTemplates.PROJECT_SUCCESS
        assert MessageTemplates.PROJECT_IN_PROGRESS
        assert MessageTemplates.PROJECT_TIMED_OUT
        assert MessageTemplates.PROJECT_COMPLETED
        assert MessageTemplates.PROJECT_COMPLETED_WITH_CODE
        assert MessageTemplates.SUMMARY_TEMPLATE
