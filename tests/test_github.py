"""
Tests for GitHub integration utilities.

This module tests the GitHubManager class which handles repository creation,
.gitignore copying, git operations, and pushing projects to GitHub.
"""

import subprocess
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pytest
from github import GithubException

from src.utils.github import (
    GitHubManager,
    MAX_DESCRIPTION_LENGTH,
    DISCORD_INVALID_WEBHOOK_TOKEN,
    GIT_OPERATION_TIMEOUT
)


class TestGitHubManagerInit:
    """Tests for GitHubManager initialization and configuration."""
    
    def test_init_and_configuration(self):
        """Test GitHubManager initialization and configuration options.

        Tests that GitHubManager correctly:
            - Loads config values (enabled, token, username) from environment
            - Works when GitHub is disabled
            - Returns correct is_configured() values for various states
            - Accepts custom credentials via dependency injection
            - Can be explicitly disabled
        """
        # Loads config from environment
        with patch('src.utils.github.GITHUB_ENABLED', True), \
             patch('src.utils.github.GITHUB_TOKEN', 'test_token'), \
             patch('src.utils.github.GITHUB_USERNAME', 'test_user'):
            manager = GitHubManager()
            assert manager.enabled is True
            assert manager.token == 'test_token'
            assert manager.username == 'test_user'
            assert manager.is_configured() is True
        
        # Works when disabled
        with patch('src.utils.github.GITHUB_ENABLED', False), \
             patch('src.utils.github.GITHUB_TOKEN', None), \
             patch('src.utils.github.GITHUB_USERNAME', None):
            manager = GitHubManager()
            assert manager.enabled is False
            assert manager.is_configured() is False
        
        # is_configured False when token missing
        with patch('src.utils.github.GITHUB_ENABLED', True), \
             patch('src.utils.github.GITHUB_TOKEN', None), \
             patch('src.utils.github.GITHUB_USERNAME', 'user'):
            manager = GitHubManager()
            assert manager.is_configured() is False
        
        # is_configured False when username missing
        with patch('src.utils.github.GITHUB_ENABLED', True), \
             patch('src.utils.github.GITHUB_TOKEN', 'token'), \
             patch('src.utils.github.GITHUB_USERNAME', None):
            manager = GitHubManager()
            assert manager.is_configured() is False
        
        # is_configured False with empty strings
        with patch('src.utils.github.GITHUB_ENABLED', True), \
             patch('src.utils.github.GITHUB_TOKEN', ''), \
             patch('src.utils.github.GITHUB_USERNAME', ''):
            manager = GitHubManager()
            assert manager.is_configured() is False
        
        # Accepts custom credentials (dependency injection)
        manager = GitHubManager(token="custom_token", username="custom_user", enabled=True)
        assert manager.token == "custom_token"
        assert manager.username == "custom_user"
        assert manager.enabled is True
        
        # Can be explicitly disabled
        manager = GitHubManager(enabled=False)
        assert manager.enabled is False
        assert manager.github is None


class TestGitHubProperty:
    """Tests for the github property lazy loading behavior."""
    
    def test_github_property(self):
        """Test github property lazy loading and caching behavior.

        Tests that the github property:
            - Returns None when disabled
            - Lazy loads client on first access
            - Caches client (only creates once)
            - Returns None when token is missing
        """
        # Returns None when disabled
        with patch('src.utils.github.GITHUB_ENABLED', False), \
             patch('src.utils.github.GITHUB_TOKEN', 'token'), \
             patch('src.utils.github.GITHUB_USERNAME', 'user'):
            manager = GitHubManager()
            assert manager.github is None
        
        # Lazy loads and caches
        with patch('src.utils.github.GITHUB_ENABLED', True), \
             patch('src.utils.github.GITHUB_TOKEN', 'test_token'), \
             patch('src.utils.github.GITHUB_USERNAME', 'test_user'), \
             patch('src.utils.github.Github') as mock_github:
            manager = GitHubManager()
            _ = manager.github
            _ = manager.github  # Second access
            mock_github.assert_called_once_with('test_token')  # Only created once
        
        # Returns None without token
        with patch('src.utils.github.GITHUB_ENABLED', True), \
             patch('src.utils.github.GITHUB_TOKEN', None), \
             patch('src.utils.github.GITHUB_USERNAME', 'test_user'), \
             patch('src.utils.github.Github') as mock_github:
            manager = GitHubManager()
            assert manager.github is None
            mock_github.assert_not_called()


class TestCopyGitignore:
    """Tests for copy_gitignore method."""
    
    def test_copy_gitignore(self, tmp_path):
        """Test copy_gitignore method for copying .gitignore files.

        Args:
            tmp_path: Pytest fixture providing a temporary directory path.

        Tests that copy_gitignore:
            - Successfully copies .gitignore to project directory
            - Returns False when source doesn't exist
            - Handles exceptions (e.g., permission errors) gracefully
        """
        # Success case
        with patch('src.utils.github.GITHUB_ENABLED', True), \
             patch('src.utils.github.GITHUB_TOKEN', 'token'), \
             patch('src.utils.github.GITHUB_USERNAME', 'user'), \
             patch('src.utils.github.BASE_DIR', tmp_path):
            source = tmp_path / ".gitignore"
            source.write_text("*.pyc\n__pycache__/\n")
            
            project_dir = tmp_path / "project"
            project_dir.mkdir()
            
            manager = GitHubManager()
            assert manager.copy_gitignore(project_dir) is True
            assert (project_dir / ".gitignore").read_text() == "*.pyc\n__pycache__/\n"
        
        # Source not found
        with patch('src.utils.github.GITHUB_ENABLED', True), \
             patch('src.utils.github.GITHUB_TOKEN', 'token'), \
             patch('src.utils.github.GITHUB_USERNAME', 'user'), \
             patch('src.utils.github.BASE_DIR', tmp_path / "nonexistent"):
            project_dir2 = tmp_path / "project2"
            project_dir2.mkdir()
            
            manager = GitHubManager()
            assert manager.copy_gitignore(project_dir2) is False
        
        # Exception handling
        with patch('src.utils.github.GITHUB_ENABLED', True), \
             patch('src.utils.github.GITHUB_TOKEN', 'token'), \
             patch('src.utils.github.GITHUB_USERNAME', 'user'), \
             patch('src.utils.github.BASE_DIR', tmp_path), \
             patch('shutil.copy2', side_effect=PermissionError("Access denied")):
            source = tmp_path / ".gitignore"
            source.write_text("*.pyc\n")
            
            project_dir3 = tmp_path / "project3"
            project_dir3.mkdir()
            
            manager = GitHubManager()
            assert manager.copy_gitignore(project_dir3) is False


class TestCreateRepository:
    """Tests for create_repository method covering success and error cases."""
    
    def test_create_repository(self):
        """Test create_repository method for GitHub repository creation.

        Tests that create_repository:
            - Returns failure when not configured
            - Successfully creates repository with proper parameters
            - Handles GithubException errors
            - Handles generic exceptions
            - Handles detailed errors list from GitHub API
        """
        # Not configured
        with patch('src.utils.github.GITHUB_ENABLED', False), \
             patch('src.utils.github.GITHUB_TOKEN', None), \
             patch('src.utils.github.GITHUB_USERNAME', None):
            manager = GitHubManager()
            success, message, url = manager.create_repository("test-repo")
            assert success is False
            assert "not configured" in message
            assert url is None
        
        # Success case
        mock_repo = Mock()
        mock_repo.full_name = "user/test-repo"
        mock_repo.html_url = "https://github.com/user/test-repo"
        mock_repo.clone_url = "https://github.com/user/test-repo.git"
        
        mock_user = Mock()
        mock_user.create_repo.return_value = mock_repo
        
        mock_github = Mock()
        mock_github.get_user.return_value = mock_user
        
        with patch('src.utils.github.GITHUB_ENABLED', True), \
             patch('src.utils.github.GITHUB_TOKEN', 'token'), \
             patch('src.utils.github.GITHUB_USERNAME', 'user'), \
             patch('src.utils.github.Github', return_value=mock_github):
            manager = GitHubManager()
            success, message, url = manager.create_repository(
                "test-repo", description="Test description", private=True
            )
            assert success is True
            assert "https://github.com/user/test-repo" in message
            assert url == "https://github.com/user/test-repo.git"
            mock_user.create_repo.assert_called_once_with(
                name="test-repo", description="Test description",
                private=True, auto_init=False
            )
        
        # GithubException
        mock_user2 = Mock()
        mock_user2.create_repo.side_effect = GithubException(
            422, {"message": "Repository already exists"}, None
        )
        mock_github2 = Mock()
        mock_github2.get_user.return_value = mock_user2
        
        with patch('src.utils.github.GITHUB_ENABLED', True), \
             patch('src.utils.github.GITHUB_TOKEN', 'token'), \
             patch('src.utils.github.GITHUB_USERNAME', 'user'), \
             patch('src.utils.github.Github', return_value=mock_github2):
            manager = GitHubManager()
            success, message, url = manager.create_repository("test-repo")
            assert success is False
            assert "GitHub API error" in message
        
        # Generic exception
        mock_github3 = Mock()
        mock_github3.get_user.side_effect = Exception("Network error")
        
        with patch('src.utils.github.GITHUB_ENABLED', True), \
             patch('src.utils.github.GITHUB_TOKEN', 'token'), \
             patch('src.utils.github.GITHUB_USERNAME', 'user'), \
             patch('src.utils.github.Github', return_value=mock_github3):
            manager = GitHubManager()
            success, message, url = manager.create_repository("test-repo")
            assert success is False
            assert "Failed to create repository" in message
        
        # Detailed errors list
        mock_user4 = Mock()
        mock_user4.create_repo.side_effect = GithubException(
            422, {"message": "Validation Failed", "errors": [
                {"field": "name", "code": "already_exists"}
            ]}, None
        )
        mock_github4 = Mock()
        mock_github4.get_user.return_value = mock_user4
        
        with patch('src.utils.github.GITHUB_ENABLED', True), \
             patch('src.utils.github.GITHUB_TOKEN', 'token'), \
             patch('src.utils.github.GITHUB_USERNAME', 'user'), \
             patch('src.utils.github.Github', return_value=mock_github4):
            manager = GitHubManager()
            success, message, url = manager.create_repository("test-repo")
            assert success is False
            assert "Details:" in message


class TestInitAndPush:
    """Tests for init_and_push method covering git operations."""
    
    def test_init_and_push(self, tmp_path):
        """Test init_and_push method for git initialization and push operations.

        Args:
            tmp_path: Pytest fixture providing a temporary directory path.

        Tests that init_and_push:
            - Returns failure when not configured
            - Successfully initializes and pushes repository
            - Handles git command failures
            - Handles timeout errors
            - Handles generic exceptions
            - Uses noreply email when user email is missing
        """
        # Not configured
        with patch('src.utils.github.GITHUB_ENABLED', False), \
             patch('src.utils.github.GITHUB_TOKEN', None), \
             patch('src.utils.github.GITHUB_USERNAME', None):
            manager = GitHubManager()
            success, message = manager.init_and_push(tmp_path, "test-repo")
            assert success is False
            assert "not configured" in message
        
        # Success case
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stderr = ""
        
        mock_user = Mock()
        mock_user.login = "testuser"
        mock_user.name = "Test User"
        mock_user.email = "test@example.com"
        
        mock_github = Mock()
        mock_github.get_user.return_value = mock_user
        
        with patch('src.utils.github.GITHUB_ENABLED', True), \
             patch('src.utils.github.GITHUB_TOKEN', 'token'), \
             patch('src.utils.github.GITHUB_USERNAME', 'user'), \
             patch('src.utils.github.Github', return_value=mock_github), \
             patch('subprocess.run', return_value=mock_result):
            manager = GitHubManager()
            success, message = manager.init_and_push(tmp_path, "test-repo")
            assert success is True
            assert "https://github.com/testuser/test-repo" in message
        
        # Git command fails
        mock_result_fail = Mock()
        mock_result_fail.returncode = 1
        mock_result_fail.stderr = "fatal: not a git repository"
        
        with patch('src.utils.github.GITHUB_ENABLED', True), \
             patch('src.utils.github.GITHUB_TOKEN', 'token'), \
             patch('src.utils.github.GITHUB_USERNAME', 'user'), \
             patch('src.utils.github.Github', return_value=mock_github), \
             patch('subprocess.run', return_value=mock_result_fail):
            manager = GitHubManager()
            success, message = manager.init_and_push(tmp_path, "test-repo")
            assert success is False
            assert "Git command failed" in message
        
        # Timeout
        with patch('src.utils.github.GITHUB_ENABLED', True), \
             patch('src.utils.github.GITHUB_TOKEN', 'token'), \
             patch('src.utils.github.GITHUB_USERNAME', 'user'), \
             patch('src.utils.github.Github', return_value=mock_github), \
             patch('subprocess.run', side_effect=subprocess.TimeoutExpired("git", GIT_OPERATION_TIMEOUT)):
            manager = GitHubManager()
            success, message = manager.init_and_push(tmp_path, "test-repo")
            assert success is False
            assert "timed out" in message
        
        # Generic exception
        mock_github_error = Mock()
        mock_github_error.get_user.side_effect = Exception("Unexpected error")
        
        with patch('src.utils.github.GITHUB_ENABLED', True), \
             patch('src.utils.github.GITHUB_TOKEN', 'token'), \
             patch('src.utils.github.GITHUB_USERNAME', 'user'), \
             patch('src.utils.github.Github', return_value=mock_github_error):
            manager = GitHubManager()
            success, message = manager.init_and_push(tmp_path, "test-repo")
            assert success is False
            assert "Failed to push to GitHub" in message
        
        # Uses noreply email when email missing
        mock_user_no_email = Mock()
        mock_user_no_email.login = "testuser"
        mock_user_no_email.name = "Test User"
        mock_user_no_email.email = None
        
        mock_github_no_email = Mock()
        mock_github_no_email.get_user.return_value = mock_user_no_email
        
        with patch('src.utils.github.GITHUB_ENABLED', True), \
             patch('src.utils.github.GITHUB_TOKEN', 'token'), \
             patch('src.utils.github.GITHUB_USERNAME', 'user'), \
             patch('src.utils.github.Github', return_value=mock_github_no_email), \
             patch('subprocess.run', return_value=mock_result) as mock_run:
            manager = GitHubManager()
            success, message = manager.init_and_push(tmp_path, "test-repo")
            assert success is True
            calls = mock_run.call_args_list
            email_config_call = [c for c in calls if 'user.email' in c[0][0]]
            assert len(email_config_call) > 0
            assert 'testuser@users.noreply.github.com' in email_config_call[0][0][0]


class TestCreateAndPushProject:
    """Tests for create_and_push_project method (full workflow)."""
    
    def test_create_and_push_project(self, tmp_path):
        """Test create_and_push_project method for full project workflow.

        Args:
            tmp_path: Pytest fixture providing a temporary directory path.

        Tests that create_and_push_project:
            - Returns failure when not configured
            - Successfully creates and pushes project
            - Handles repo creation failure
            - Handles push failure
            - Handles get_user failure
        """
        # Not configured
        with patch('src.utils.github.GITHUB_ENABLED', False), \
             patch('src.utils.github.GITHUB_TOKEN', None), \
             patch('src.utils.github.GITHUB_USERNAME', None):
            manager = GitHubManager()
            success, message, url = manager.create_and_push_project(tmp_path, "test-repo")
            assert success is False
            assert "not configured" in message
            assert url is None
        
        # Success case
        mock_repo = Mock()
        mock_repo.full_name = "testuser/test-repo"
        mock_repo.html_url = "https://github.com/testuser/test-repo"
        mock_repo.clone_url = "https://github.com/testuser/test-repo.git"
        
        mock_user = Mock()
        mock_user.login = "testuser"
        mock_user.name = "Test User"
        mock_user.email = "test@example.com"
        mock_user.create_repo.return_value = mock_repo
        
        mock_github = Mock()
        mock_github.get_user.return_value = mock_user
        
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stderr = ""
        
        with patch('src.utils.github.GITHUB_ENABLED', True), \
             patch('src.utils.github.GITHUB_TOKEN', 'token'), \
             patch('src.utils.github.GITHUB_USERNAME', 'user'), \
             patch('src.utils.github.BASE_DIR', tmp_path), \
             patch('src.utils.github.Github', return_value=mock_github), \
             patch('subprocess.run', return_value=mock_result):
            (tmp_path / ".gitignore").write_text("*.pyc\n")
            project_dir = tmp_path / "project"
            project_dir.mkdir()
            
            manager = GitHubManager()
            success, message, url = manager.create_and_push_project(
                project_dir, "test-repo", "Test description"
            )
            assert success is True
            assert "https://github.com/testuser/test-repo" in message
            assert url == "https://github.com/testuser/test-repo"
        
        # Repo creation fails
        mock_user_fail = Mock()
        mock_user_fail.login = "testuser"
        mock_user_fail.create_repo.side_effect = GithubException(
            422, {"message": "Repository already exists"}, None
        )
        mock_github_fail = Mock()
        mock_github_fail.get_user.return_value = mock_user_fail
        
        with patch('src.utils.github.GITHUB_ENABLED', True), \
             patch('src.utils.github.GITHUB_TOKEN', 'token'), \
             patch('src.utils.github.GITHUB_USERNAME', 'user'), \
             patch('src.utils.github.BASE_DIR', tmp_path), \
             patch('src.utils.github.Github', return_value=mock_github_fail):
            project_dir2 = tmp_path / "project2"
            project_dir2.mkdir()
            
            manager = GitHubManager()
            success, message, url = manager.create_and_push_project(project_dir2, "test-repo")
            assert success is False
            assert "GitHub API error" in message
        
        # Push fails
        mock_user_push = Mock()
        mock_user_push.login = "testuser"
        mock_user_push.name = "Test User"
        mock_user_push.email = "test@example.com"
        mock_user_push.create_repo.return_value = mock_repo
        
        mock_github_push = Mock()
        mock_github_push.get_user.return_value = mock_user_push
        
        mock_result_fail = Mock()
        mock_result_fail.returncode = 1
        mock_result_fail.stderr = "push failed"
        
        with patch('src.utils.github.GITHUB_ENABLED', True), \
             patch('src.utils.github.GITHUB_TOKEN', 'token'), \
             patch('src.utils.github.GITHUB_USERNAME', 'user'), \
             patch('src.utils.github.BASE_DIR', tmp_path), \
             patch('src.utils.github.Github', return_value=mock_github_push), \
             patch('subprocess.run', return_value=mock_result_fail):
            project_dir3 = tmp_path / "project3"
            project_dir3.mkdir()
            
            manager = GitHubManager()
            success, message, url = manager.create_and_push_project(project_dir3, "test-repo")
            assert success is False
            assert "Git command failed" in message
        
        # Get user fails
        mock_github_user_fail = Mock()
        mock_github_user_fail.get_user.side_effect = Exception("API error")
        
        with patch('src.utils.github.GITHUB_ENABLED', True), \
             patch('src.utils.github.GITHUB_TOKEN', 'token'), \
             patch('src.utils.github.GITHUB_USERNAME', 'user'), \
             patch('src.utils.github.BASE_DIR', tmp_path), \
             patch('src.utils.github.Github', return_value=mock_github_user_fail):
            project_dir4 = tmp_path / "project4"
            project_dir4.mkdir()
            
            manager = GitHubManager()
            success, message, url = manager.create_and_push_project(project_dir4, "test-repo")
            assert success is False
            assert "Failed to get GitHub user info" in message


class TestGitHubManagerSingleton:
    """Tests for the github_manager singleton."""
    
    def test_github_manager_singleton(self):
        """Test that github_manager singleton exists and is properly typed.

        Verifies that the github_manager singleton is not None and is an
        instance of GitHubManager.
        """
        from src.utils.github import github_manager
        assert github_manager is not None
        assert isinstance(github_manager, GitHubManager)


class TestSanitizeDescription:
    """Tests for sanitize_description method."""
    
    def test_sanitize_description(self):
        """Test sanitize_description method for cleaning repository descriptions.

        Tests that sanitize_description correctly:
            - Removes quotes from descriptions
            - Removes control characters
            - Removes non-ASCII unicode (emojis)
            - Truncates long descriptions with ellipsis
            - Replaces multiple whitespace with single space
        """
        with patch('src.utils.github.GITHUB_ENABLED', False):
            manager = GitHubManager()
            
            # Removes quotes
            assert manager.sanitize_description('"A cool project"') == "A cool project"
            
            # Removes control chars
            result = manager.sanitize_description("A project\x00\x01\x02")
            assert "\x00" not in result
            assert "A project" in result
            
            # Removes unicode/emojis
            result = manager.sanitize_description("A project 🚀 with emoji")
            assert "🚀" not in result
            
            # Truncates long descriptions
            long_desc = "x" * 400
            result = manager.sanitize_description(long_desc)
            assert len(result) <= MAX_DESCRIPTION_LENGTH
            assert result.endswith("...")
            
            # Replaces multiple whitespace
            assert manager.sanitize_description("A   project   with    spaces") == "A project with spaces"


class TestGitHubConstants:
    """Tests for GitHub module constants."""
    
    def test_constants(self):
        """Test GitHub module constants have expected values.

        Verifies that the following constants are correctly defined:
            - DISCORD_INVALID_WEBHOOK_TOKEN is 50027
            - MAX_DESCRIPTION_LENGTH is 350
            - GIT_OPERATION_TIMEOUT is 300 (5 minutes)
        """
        assert isinstance(DISCORD_INVALID_WEBHOOK_TOKEN, int)
        assert DISCORD_INVALID_WEBHOOK_TOKEN == 50027
        
        assert isinstance(MAX_DESCRIPTION_LENGTH, int)
        assert MAX_DESCRIPTION_LENGTH == 350
        
        assert isinstance(GIT_OPERATION_TIMEOUT, int)
        assert GIT_OPERATION_TIMEOUT == 300


class TestInitAndPushLogging:
    """Tests for init_and_push logging behavior."""
    
    def test_init_and_push_logs(self, tmp_path):
        """Test that init_and_push logs debug information for git commands.

        Args:
            tmp_path: Pytest fixture providing a temporary directory path.

        Verifies that debug logging is called at least once during git operations.
        """
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stderr = ""
        
        mock_user = Mock()
        mock_user.login = "testuser"
        mock_user.name = "Test User"
        mock_user.email = "test@example.com"
        
        mock_github = Mock()
        mock_github.get_user.return_value = mock_user
        
        with patch('src.utils.github.GITHUB_ENABLED', True), \
             patch('src.utils.github.GITHUB_TOKEN', 'token'), \
             patch('src.utils.github.GITHUB_USERNAME', 'user'), \
             patch('src.utils.github.Github', return_value=mock_github), \
             patch('subprocess.run', return_value=mock_result), \
             patch('src.utils.github.logger') as mock_logger:
            manager = GitHubManager()
            success, message = manager.init_and_push(tmp_path, "test-repo")
            
            assert success is True
            assert mock_logger.debug.call_count >= 1
