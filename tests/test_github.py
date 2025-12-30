"""
Tests for GitHub integration utilities.
"""

import subprocess
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pytest
from github import GithubException

from src.utils.github import GitHubManager


class TestGitHubManagerInit:
    """Tests for GitHubManager initialization."""
    
    def test_init_loads_config(self):
        """Test that GitHubManager loads configuration on init."""
        with patch('src.utils.github.GITHUB_ENABLED', True), \
             patch('src.utils.github.GITHUB_TOKEN', 'test_token'), \
             patch('src.utils.github.GITHUB_USERNAME', 'test_user'):
            manager = GitHubManager()
            assert manager.enabled is True
            assert manager.token == 'test_token'
            assert manager.username == 'test_user'
    
    def test_init_with_disabled_github(self):
        """Test that GitHubManager works when GitHub is disabled."""
        with patch('src.utils.github.GITHUB_ENABLED', False), \
             patch('src.utils.github.GITHUB_TOKEN', None), \
             patch('src.utils.github.GITHUB_USERNAME', None):
            manager = GitHubManager()
            assert manager.enabled is False
            assert manager.token is None
            assert manager.username is None


class TestGitHubProperty:
    """Tests for the github property lazy loading."""
    
    def test_github_property_when_disabled(self):
        """Test that github property returns None when disabled."""
        with patch('src.utils.github.GITHUB_ENABLED', False), \
             patch('src.utils.github.GITHUB_TOKEN', 'token'), \
             patch('src.utils.github.GITHUB_USERNAME', 'user'):
            manager = GitHubManager()
            assert manager.github is None
    
    def test_github_property_lazy_loads(self):
        """Test that github property creates client on first access."""
        with patch('src.utils.github.GITHUB_ENABLED', True), \
             patch('src.utils.github.GITHUB_TOKEN', 'test_token'), \
             patch('src.utils.github.GITHUB_USERNAME', 'test_user'), \
             patch('src.utils.github.Github') as mock_github:
            manager = GitHubManager()
            # Access the property
            _ = manager.github
            mock_github.assert_called_once_with('test_token')
    
    def test_github_property_caches_client(self):
        """Test that github property caches the client."""
        with patch('src.utils.github.GITHUB_ENABLED', True), \
             patch('src.utils.github.GITHUB_TOKEN', 'test_token'), \
             patch('src.utils.github.GITHUB_USERNAME', 'test_user'), \
             patch('src.utils.github.Github') as mock_github:
            manager = GitHubManager()
            # Access the property twice
            _ = manager.github
            _ = manager.github
            # Should only create once
            mock_github.assert_called_once()
    
    def test_github_property_no_token(self):
        """Test that github property handles missing token."""
        with patch('src.utils.github.GITHUB_ENABLED', True), \
             patch('src.utils.github.GITHUB_TOKEN', None), \
             patch('src.utils.github.GITHUB_USERNAME', 'test_user'), \
             patch('src.utils.github.Github') as mock_github:
            manager = GitHubManager()
            result = manager.github
            # Should not create client without token
            mock_github.assert_not_called()
            assert result is None


class TestIsConfigured:
    """Tests for is_configured method."""
    
    def test_is_configured_all_set(self):
        """Test is_configured returns True when all settings are present."""
        with patch('src.utils.github.GITHUB_ENABLED', True), \
             patch('src.utils.github.GITHUB_TOKEN', 'token'), \
             patch('src.utils.github.GITHUB_USERNAME', 'user'):
            manager = GitHubManager()
            assert manager.is_configured() is True
    
    def test_is_configured_disabled(self):
        """Test is_configured returns False when disabled."""
        with patch('src.utils.github.GITHUB_ENABLED', False), \
             patch('src.utils.github.GITHUB_TOKEN', 'token'), \
             patch('src.utils.github.GITHUB_USERNAME', 'user'):
            manager = GitHubManager()
            assert manager.is_configured() is False
    
    def test_is_configured_no_token(self):
        """Test is_configured returns False when token is missing."""
        with patch('src.utils.github.GITHUB_ENABLED', True), \
             patch('src.utils.github.GITHUB_TOKEN', None), \
             patch('src.utils.github.GITHUB_USERNAME', 'user'):
            manager = GitHubManager()
            assert manager.is_configured() is False
    
    def test_is_configured_no_username(self):
        """Test is_configured returns False when username is missing."""
        with patch('src.utils.github.GITHUB_ENABLED', True), \
             patch('src.utils.github.GITHUB_TOKEN', 'token'), \
             patch('src.utils.github.GITHUB_USERNAME', None):
            manager = GitHubManager()
            assert manager.is_configured() is False
    
    def test_is_configured_empty_strings(self):
        """Test is_configured returns False with empty strings."""
        with patch('src.utils.github.GITHUB_ENABLED', True), \
             patch('src.utils.github.GITHUB_TOKEN', ''), \
             patch('src.utils.github.GITHUB_USERNAME', ''):
            manager = GitHubManager()
            assert manager.is_configured() is False


class TestCopyGitignore:
    """Tests for copy_gitignore method."""
    
    def test_copy_gitignore_success(self, tmp_path):
        """Test successful .gitignore copy."""
        # Create a fake source .gitignore
        with patch('src.utils.github.GITHUB_ENABLED', True), \
             patch('src.utils.github.GITHUB_TOKEN', 'token'), \
             patch('src.utils.github.GITHUB_USERNAME', 'user'), \
             patch('src.utils.github.BASE_DIR', tmp_path):
            # Create source gitignore
            source = tmp_path / ".gitignore"
            source.write_text("*.pyc\n__pycache__/\n")
            
            # Create target directory
            project_dir = tmp_path / "project"
            project_dir.mkdir()
            
            manager = GitHubManager()
            result = manager.copy_gitignore(project_dir)
            
            assert result is True
            dest = project_dir / ".gitignore"
            assert dest.exists()
            assert dest.read_text() == "*.pyc\n__pycache__/\n"
    
    def test_copy_gitignore_source_not_found(self, tmp_path):
        """Test copy_gitignore when source doesn't exist."""
        with patch('src.utils.github.GITHUB_ENABLED', True), \
             patch('src.utils.github.GITHUB_TOKEN', 'token'), \
             patch('src.utils.github.GITHUB_USERNAME', 'user'), \
             patch('src.utils.github.BASE_DIR', tmp_path):
            # No source gitignore created
            project_dir = tmp_path / "project"
            project_dir.mkdir()
            
            manager = GitHubManager()
            result = manager.copy_gitignore(project_dir)
            
            assert result is False
    
    def test_copy_gitignore_exception(self, tmp_path):
        """Test copy_gitignore handles exceptions."""
        with patch('src.utils.github.GITHUB_ENABLED', True), \
             patch('src.utils.github.GITHUB_TOKEN', 'token'), \
             patch('src.utils.github.GITHUB_USERNAME', 'user'), \
             patch('src.utils.github.BASE_DIR', tmp_path), \
             patch('shutil.copy2', side_effect=PermissionError("Access denied")):
            # Create source gitignore
            source = tmp_path / ".gitignore"
            source.write_text("*.pyc\n")
            
            project_dir = tmp_path / "project"
            project_dir.mkdir()
            
            manager = GitHubManager()
            result = manager.copy_gitignore(project_dir)
            
            assert result is False


class TestCreateRepository:
    """Tests for create_repository method."""
    
    def test_create_repository_not_configured(self):
        """Test create_repository when not configured."""
        with patch('src.utils.github.GITHUB_ENABLED', False), \
             patch('src.utils.github.GITHUB_TOKEN', None), \
             patch('src.utils.github.GITHUB_USERNAME', None):
            manager = GitHubManager()
            success, message, url = manager.create_repository("test-repo")
            
            assert success is False
            assert "not configured" in message
            assert url is None
    
    def test_create_repository_success(self):
        """Test successful repository creation."""
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
                "test-repo", 
                description="Test description",
                private=True
            )
            
            assert success is True
            assert "https://github.com/user/test-repo" in message
            assert url == "https://github.com/user/test-repo.git"
            mock_user.create_repo.assert_called_once_with(
                name="test-repo",
                description="Test description",
                private=True,
                auto_init=False
            )
    
    def test_create_repository_github_exception(self):
        """Test create_repository handles GithubException."""
        mock_github = Mock()
        mock_user = Mock()
        mock_user.create_repo.side_effect = GithubException(
            422, {"message": "Repository already exists"}, None
        )
        mock_github.get_user.return_value = mock_user
        
        with patch('src.utils.github.GITHUB_ENABLED', True), \
             patch('src.utils.github.GITHUB_TOKEN', 'token'), \
             patch('src.utils.github.GITHUB_USERNAME', 'user'), \
             patch('src.utils.github.Github', return_value=mock_github):
            manager = GitHubManager()
            success, message, url = manager.create_repository("test-repo")
            
            assert success is False
            assert "GitHub API error" in message
            assert url is None
    
    def test_create_repository_generic_exception(self):
        """Test create_repository handles generic exceptions."""
        mock_github = Mock()
        mock_github.get_user.side_effect = Exception("Network error")
        
        with patch('src.utils.github.GITHUB_ENABLED', True), \
             patch('src.utils.github.GITHUB_TOKEN', 'token'), \
             patch('src.utils.github.GITHUB_USERNAME', 'user'), \
             patch('src.utils.github.Github', return_value=mock_github):
            manager = GitHubManager()
            success, message, url = manager.create_repository("test-repo")
            
            assert success is False
            assert "Failed to create repository" in message
            assert url is None


class TestInitAndPush:
    """Tests for init_and_push method."""
    
    def test_init_and_push_not_configured(self, tmp_path):
        """Test init_and_push when not configured."""
        with patch('src.utils.github.GITHUB_ENABLED', False), \
             patch('src.utils.github.GITHUB_TOKEN', None), \
             patch('src.utils.github.GITHUB_USERNAME', None):
            manager = GitHubManager()
            success, message = manager.init_and_push(tmp_path, "test-repo")
            
            assert success is False
            assert "not configured" in message
    
    def test_init_and_push_success(self, tmp_path):
        """Test successful init and push."""
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
    
    def test_init_and_push_git_command_fails(self, tmp_path):
        """Test init_and_push when git command fails."""
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stderr = "fatal: not a git repository"
        
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
            
            assert success is False
            assert "Git command failed" in message
    
    def test_init_and_push_timeout(self, tmp_path):
        """Test init_and_push handles timeout."""
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
             patch('subprocess.run', side_effect=subprocess.TimeoutExpired("git", 60)):
            manager = GitHubManager()
            success, message = manager.init_and_push(tmp_path, "test-repo")
            
            assert success is False
            assert "timed out" in message
    
    def test_init_and_push_generic_exception(self, tmp_path):
        """Test init_and_push handles generic exceptions."""
        mock_github = Mock()
        mock_github.get_user.side_effect = Exception("Unexpected error")
        
        with patch('src.utils.github.GITHUB_ENABLED', True), \
             patch('src.utils.github.GITHUB_TOKEN', 'token'), \
             patch('src.utils.github.GITHUB_USERNAME', 'user'), \
             patch('src.utils.github.Github', return_value=mock_github):
            manager = GitHubManager()
            success, message = manager.init_and_push(tmp_path, "test-repo")
            
            assert success is False
            assert "Failed to push to GitHub" in message
    
    def test_init_and_push_uses_noreply_email_when_email_missing(self, tmp_path):
        """Test init_and_push uses noreply email when user email is None."""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stderr = ""
        
        mock_user = Mock()
        mock_user.login = "testuser"
        mock_user.name = "Test User"
        mock_user.email = None  # No email set
        
        mock_github = Mock()
        mock_github.get_user.return_value = mock_user
        
        with patch('src.utils.github.GITHUB_ENABLED', True), \
             patch('src.utils.github.GITHUB_TOKEN', 'token'), \
             patch('src.utils.github.GITHUB_USERNAME', 'user'), \
             patch('src.utils.github.Github', return_value=mock_github), \
             patch('subprocess.run', return_value=mock_result) as mock_run:
            manager = GitHubManager()
            success, message = manager.init_and_push(tmp_path, "test-repo")
            
            assert success is True
            # Check that git config user.email was called with noreply email
            calls = mock_run.call_args_list
            email_config_call = [c for c in calls if 'user.email' in c[0][0]]
            assert len(email_config_call) > 0
            assert 'testuser@users.noreply.github.com' in email_config_call[0][0][0]


class TestCreateAndPushProject:
    """Tests for create_and_push_project method."""
    
    def test_create_and_push_not_configured(self, tmp_path):
        """Test create_and_push_project when not configured."""
        with patch('src.utils.github.GITHUB_ENABLED', False), \
             patch('src.utils.github.GITHUB_TOKEN', None), \
             patch('src.utils.github.GITHUB_USERNAME', None):
            manager = GitHubManager()
            success, message, url = manager.create_and_push_project(
                tmp_path, "test-repo"
            )
            
            assert success is False
            assert "not configured" in message
            assert url is None
    
    def test_create_and_push_success(self, tmp_path):
        """Test successful create_and_push_project."""
        # Create source gitignore
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
            # Create source gitignore
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
    
    def test_create_and_push_repo_creation_fails(self, tmp_path):
        """Test create_and_push_project when repo creation fails."""
        mock_user = Mock()
        mock_user.login = "testuser"
        mock_user.create_repo.side_effect = GithubException(
            422, {"message": "Repository already exists"}, None
        )
        
        mock_github = Mock()
        mock_github.get_user.return_value = mock_user
        
        with patch('src.utils.github.GITHUB_ENABLED', True), \
             patch('src.utils.github.GITHUB_TOKEN', 'token'), \
             patch('src.utils.github.GITHUB_USERNAME', 'user'), \
             patch('src.utils.github.BASE_DIR', tmp_path), \
             patch('src.utils.github.Github', return_value=mock_github):
            (tmp_path / ".gitignore").write_text("*.pyc\n")
            project_dir = tmp_path / "project"
            project_dir.mkdir()
            
            manager = GitHubManager()
            success, message, url = manager.create_and_push_project(
                project_dir, "test-repo"
            )
            
            assert success is False
            assert "GitHub API error" in message
            assert url is None
    
    def test_create_and_push_push_fails(self, tmp_path):
        """Test create_and_push_project when push fails."""
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
        mock_result.returncode = 1
        mock_result.stderr = "push failed"
        
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
                project_dir, "test-repo"
            )
            
            assert success is False
            assert "Git command failed" in message
            assert url is None
    
    def test_create_and_push_get_user_fails(self, tmp_path):
        """Test create_and_push_project when getting user info fails."""
        mock_github = Mock()
        mock_github.get_user.side_effect = Exception("API error")
        
        with patch('src.utils.github.GITHUB_ENABLED', True), \
             patch('src.utils.github.GITHUB_TOKEN', 'token'), \
             patch('src.utils.github.GITHUB_USERNAME', 'user'), \
             patch('src.utils.github.BASE_DIR', tmp_path), \
             patch('src.utils.github.Github', return_value=mock_github):
            (tmp_path / ".gitignore").write_text("*.pyc\n")
            project_dir = tmp_path / "project"
            project_dir.mkdir()
            
            manager = GitHubManager()
            success, message, url = manager.create_and_push_project(
                project_dir, "test-repo"
            )
            
            assert success is False
            assert "Failed to get GitHub user info" in message
            assert url is None


class TestGitHubManagerSingleton:
    """Tests for the github_manager singleton."""
    
    def test_github_manager_singleton_exists(self):
        """Test that github_manager singleton is created."""
        from src.utils.github import github_manager
        assert github_manager is not None
        assert isinstance(github_manager, GitHubManager)


class TestSanitizeDescription:
    """Tests for sanitize_description method."""
    
    def test_sanitize_description_removes_quotes(self):
        """Test that quotes are removed from description."""
        with patch('src.utils.github.GITHUB_ENABLED', False):
            manager = GitHubManager()
            result = manager.sanitize_description('"A cool project"')
            
            assert result == "A cool project"
    
    def test_sanitize_description_removes_control_chars(self):
        """Test that control characters are removed."""
        with patch('src.utils.github.GITHUB_ENABLED', False):
            manager = GitHubManager()
            result = manager.sanitize_description("A project\x00\x01\x02")
            
            assert "\x00" not in result
            assert "A project" in result
    
    def test_sanitize_description_removes_unicode(self):
        """Test that non-ASCII unicode is removed."""
        with patch('src.utils.github.GITHUB_ENABLED', False):
            manager = GitHubManager()
            result = manager.sanitize_description("A project 🚀 with emoji")
            
            assert "🚀" not in result
            assert "A project" in result
    
    def test_sanitize_description_truncates_long(self):
        """Test that long descriptions are truncated."""
        with patch('src.utils.github.GITHUB_ENABLED', False):
            manager = GitHubManager()
            long_desc = "x" * 400
            result = manager.sanitize_description(long_desc)
            
            assert len(result) <= manager.MAX_DESCRIPTION_LENGTH
            assert result.endswith("...")
    
    def test_sanitize_description_replaces_whitespace(self):
        """Test that multiple whitespace is replaced."""
        with patch('src.utils.github.GITHUB_ENABLED', False):
            manager = GitHubManager()
            result = manager.sanitize_description("A   project   with    spaces")
            
            assert "   " not in result
            assert "A project with spaces" == result


class TestCreateRepositoryErrors:
    """Tests for create_repository error handling with detailed errors."""
    
    def test_create_repository_with_errors_list(self):
        """Test create_repository with detailed errors list (lines 160-164)."""
        mock_github = Mock()
        mock_user = Mock()
        mock_user.create_repo.side_effect = GithubException(
            422, 
            {
                "message": "Validation Failed",
                "errors": [
                    {"field": "name", "code": "already_exists"},
                    {"field": "description", "code": "invalid"}
                ],
                "documentation_url": "https://docs.github.com/rest"
            }, 
            None
        )
        mock_github.get_user.return_value = mock_user
        
        with patch('src.utils.github.GITHUB_ENABLED', True), \
             patch('src.utils.github.GITHUB_TOKEN', 'token'), \
             patch('src.utils.github.GITHUB_USERNAME', 'user'), \
             patch('src.utils.github.Github', return_value=mock_github):
            manager = GitHubManager()
            success, message, url = manager.create_repository("test-repo")
            
            assert success is False
            assert "Details:" in message
            assert url is None


class TestInitAndPushLogging:
    """Tests for init_and_push logging behavior."""
    
    def test_init_and_push_logs_safe_command(self, tmp_path):
        """Test init_and_push logs safe command for remote add (line 232-237)."""
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
            # Verify debug logging happened
            assert mock_logger.debug.call_count >= 1
