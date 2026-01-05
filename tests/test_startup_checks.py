"""
Tests for startup_checks module.
"""

import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from src.utils.startup_checks import (
    CheckStatus,
    CheckResult,
    StartupChecker,
    run_startup_checks,
)


class TestCheckStatus:
    """Tests for CheckStatus enum."""
    
    def test_status_values(self):
        """Test that all expected status values exist.

        Verifies that the CheckStatus enum contains PASS, WARN, FAIL,
        and SKIP values with their expected string representations.
        """
        assert CheckStatus.PASS.value == "PASS"
        assert CheckStatus.WARN.value == "WARN"
        assert CheckStatus.FAIL.value == "FAIL"
        assert CheckStatus.SKIP.value == "SKIP"


class TestCheckResult:
    """Tests for CheckResult dataclass."""
    
    def test_create_result_with_details(self):
        """Test creating a result with details.

        Verifies that a CheckResult can be created with all fields
        including optional details, and that all values are stored correctly.
        """
        result = CheckResult(
            name="Test Check",
            status=CheckStatus.PASS,
            message="All good",
            details="Extra info"
        )
        assert result.name == "Test Check"
        assert result.status == CheckStatus.PASS
        assert result.message == "All good"
        assert result.details == "Extra info"
    
    def test_create_result_without_details(self):
        """Test creating a result without details.

        Verifies that a CheckResult can be created without the optional
        details field and that it defaults to None.
        """
        result = CheckResult(
            name="Test Check",
            status=CheckStatus.FAIL,
            message="Something failed"
        )
        assert result.details is None


class TestStartupChecker:
    """Tests for StartupChecker class."""
    
    @pytest.fixture
    def checker(self):
        """Create a fresh startup checker.

        Returns:
            StartupChecker: A new StartupChecker instance for testing.
        """
        return StartupChecker()
    
    def test_init(self, checker):
        """Test initialization.

        Args:
            checker: The StartupChecker fixture instance.

        Verifies that a new StartupChecker has an empty results list.
        """
        assert checker.results == []
    
    def test_add_result(self, checker):
        """Test adding a result.

        Args:
            checker: The StartupChecker fixture instance.

        Verifies that _add_result correctly creates and stores a CheckResult.
        """
        result = checker._add_result(
            name="Test",
            status=CheckStatus.PASS,
            message="Test message",
            details="Test details"
        )
        assert len(checker.results) == 1
        assert result.name == "Test"
        assert checker.results[0] is result
    
    # Discord token checks
    @patch('src.utils.startup_checks.DISCORD_BOT_TOKEN', None)
    def test_check_discord_token_missing(self, checker):
        """Test Discord token check when missing.

        Args:
            checker: The StartupChecker fixture instance.

        Verifies that check_discord_token returns FAIL status when
        the DISCORD_BOT_TOKEN environment variable is not set.
        """
        result = checker.check_discord_token()
        assert result.status == CheckStatus.FAIL
        assert "not set" in result.message
    
    @patch('src.utils.startup_checks.DISCORD_BOT_TOKEN', 'short')
    def test_check_discord_token_short(self, checker):
        """Test Discord token check when too short.

        Args:
            checker: The StartupChecker fixture instance.

        Verifies that check_discord_token returns WARN status when
        the token appears to be shorter than expected.
        """
        result = checker.check_discord_token()
        assert result.status == CheckStatus.WARN
        assert "short" in result.message.lower()
    
    @patch('src.utils.startup_checks.DISCORD_BOT_TOKEN', 'a' * 60)
    def test_check_discord_token_valid(self, checker):
        """Test Discord token check when valid.

        Args:
            checker: The StartupChecker fixture instance.

        Verifies that check_discord_token returns PASS status when
        a valid-length token is configured.
        """
        result = checker.check_discord_token()
        assert result.status == CheckStatus.PASS
        assert "configured" in result.message
    
    # GitHub integration checks
    @patch('src.utils.startup_checks.GITHUB_ENABLED', False)
    def test_check_github_disabled(self, checker):
        """Test GitHub check when disabled.

        Args:
            checker: The StartupChecker fixture instance.

        Verifies that check_github_integration returns SKIP status
        when GitHub integration is disabled in configuration.
        """
        result = checker.check_github_integration()
        assert result.status == CheckStatus.SKIP
        assert "disabled" in result.message
    
    @patch('src.utils.startup_checks.GITHUB_ENABLED', True)
    @patch('src.utils.startup_checks.GITHUB_TOKEN', None)
    @patch('src.utils.startup_checks.GITHUB_USERNAME', 'test')
    def test_check_github_missing_token(self, checker):
        """Test GitHub check when token is missing.

        Args:
            checker: The StartupChecker fixture instance.

        Verifies that check_github_integration returns FAIL status
        when GITHUB_TOKEN is not set but GitHub is enabled.
        """
        result = checker.check_github_integration()
        assert result.status == CheckStatus.FAIL
        assert "GITHUB_TOKEN" in result.message
    
    @patch('src.utils.startup_checks.GITHUB_ENABLED', True)
    @patch('src.utils.startup_checks.GITHUB_TOKEN', 'test')
    @patch('src.utils.startup_checks.GITHUB_USERNAME', None)
    def test_check_github_missing_username(self, checker):
        """Test GitHub check when username is missing.

        Args:
            checker: The StartupChecker fixture instance.

        Verifies that check_github_integration returns FAIL status
        when GITHUB_USERNAME is not set but GitHub is enabled.
        """
        result = checker.check_github_integration()
        assert result.status == CheckStatus.FAIL
        assert "GITHUB_USERNAME" in result.message
    
    @patch('src.utils.startup_checks.GITHUB_ENABLED', True)
    @patch('src.utils.startup_checks.GITHUB_TOKEN', 'test-token')
    @patch('src.utils.startup_checks.GITHUB_USERNAME', 'testuser')
    def test_check_github_success(self, checker):
        """Test GitHub check when successful.

        Args:
            checker: The StartupChecker fixture instance.

        Verifies that check_github_integration returns PASS status
        when GitHub API authentication succeeds and username matches.
        """
        with patch('github.Github') as mock_gh:
            mock_user = MagicMock()
            mock_user.login = 'testuser'
            mock_gh.return_value.get_user.return_value = mock_user
            
            result = checker.check_github_integration()
            
            assert result.status == CheckStatus.PASS
            assert "testuser" in result.message
    
    @patch('src.utils.startup_checks.GITHUB_ENABLED', True)
    @patch('src.utils.startup_checks.GITHUB_TOKEN', 'test-token')
    @patch('src.utils.startup_checks.GITHUB_USERNAME', 'testuser')
    def test_check_github_username_mismatch(self, checker):
        """Test GitHub check when username doesn't match.

        Args:
            checker: The StartupChecker fixture instance.

        Verifies that check_github_integration returns WARN status
        when the authenticated user differs from GITHUB_USERNAME.
        """
        with patch('github.Github') as mock_gh:
            mock_user = MagicMock()
            mock_user.login = 'differentuser'
            mock_gh.return_value.get_user.return_value = mock_user
            
            result = checker.check_github_integration()
            
            assert result.status == CheckStatus.WARN
            assert "differentuser" in result.message
    
    @patch('src.utils.startup_checks.GITHUB_ENABLED', True)
    @patch('src.utils.startup_checks.GITHUB_TOKEN', 'test-token')
    @patch('src.utils.startup_checks.GITHUB_USERNAME', 'testuser')
    def test_check_github_api_error(self, checker):
        """Test GitHub check when API fails.

        Args:
            checker: The StartupChecker fixture instance.

        Verifies that check_github_integration returns FAIL status
        when the GitHub API returns an error (e.g., bad credentials).
        """
        from github import GithubException
        
        with patch('github.Github') as mock_gh:
            mock_gh.return_value.get_user.side_effect = GithubException(
                status=401,
                data={'message': 'Bad credentials'},
                headers={}
            )
            
            result = checker.check_github_integration()
            
            assert result.status == CheckStatus.FAIL
            assert "Bad credentials" in result.message
    
    @patch('src.utils.startup_checks.GITHUB_ENABLED', True)
    @patch('src.utils.startup_checks.GITHUB_TOKEN', 'test-token')
    @patch('src.utils.startup_checks.GITHUB_USERNAME', 'testuser')
    def test_check_github_generic_exception(self, checker):
        """Test GitHub check when a generic exception occurs.

        Args:
            checker: The StartupChecker fixture instance.

        Verifies that check_github_integration returns FAIL status
        and includes the exception type when an unexpected error occurs.
        """
        with patch('github.Github') as mock_gh:
            mock_gh.return_value.get_user.side_effect = ConnectionError("Network error")
            
            result = checker.check_github_integration()
            
            assert result.status == CheckStatus.FAIL
            assert "ConnectionError" in result.message
    
    # Azure OpenAI checks
    @patch('src.utils.startup_checks.AZURE_OPENAI_ENDPOINT', None)
    @patch('src.utils.startup_checks.AZURE_OPENAI_API_KEY', None)
    @patch('src.utils.startup_checks.AZURE_OPENAI_DEPLOYMENT_NAME', None)
    def test_check_azure_not_configured(self, checker):
        """Test Azure OpenAI check when not configured.

        Args:
            checker: The StartupChecker fixture instance.

        Verifies that check_azure_openai returns SKIP status when
        no Azure OpenAI configuration values are set.
        """
        result = checker.check_azure_openai()
        assert result.status == CheckStatus.SKIP
        assert "not configured" in result.message
    
    @patch('src.utils.startup_checks.AZURE_OPENAI_ENDPOINT', 'https://test.openai.azure.com')
    @patch('src.utils.startup_checks.AZURE_OPENAI_API_KEY', None)
    @patch('src.utils.startup_checks.AZURE_OPENAI_DEPLOYMENT_NAME', 'gpt-4')
    def test_check_azure_missing_api_key(self, checker):
        """Test Azure OpenAI check when API key is missing.

        Args:
            checker: The StartupChecker fixture instance.

        Verifies that check_azure_openai returns WARN status when
        endpoint is configured but API key is missing.
        """
        result = checker.check_azure_openai()
        assert result.status == CheckStatus.WARN
        assert "AZURE_OPENAI_API_KEY" in result.message
    
    @patch('src.utils.startup_checks.AZURE_OPENAI_ENDPOINT', 'https://test.openai.azure.com')
    @patch('src.utils.startup_checks.AZURE_OPENAI_API_KEY', 'test-key')
    @patch('src.utils.startup_checks.AZURE_OPENAI_DEPLOYMENT_NAME', 'gpt-4')
    def test_check_azure_success(self, checker):
        """Test Azure OpenAI check when successful.

        Args:
            checker: The StartupChecker fixture instance.

        Verifies that check_azure_openai returns PASS status when
        the Azure OpenAI API connection test succeeds.
        """
        with patch('openai.AzureOpenAI') as mock_client:
            mock_response = MagicMock()
            mock_client.return_value.chat.completions.create.return_value = mock_response
            
            result = checker.check_azure_openai()
            
            assert result.status == CheckStatus.PASS
            assert "gpt-4" in result.message
    
    @patch('src.utils.startup_checks.AZURE_OPENAI_ENDPOINT', 'https://test.openai.azure.com')
    @patch('src.utils.startup_checks.AZURE_OPENAI_API_KEY', 'test-key')
    @patch('src.utils.startup_checks.AZURE_OPENAI_DEPLOYMENT_NAME', 'gpt-4')
    def test_check_azure_connection_error(self, checker):
        """Test Azure OpenAI check when connection fails.

        Args:
            checker: The StartupChecker fixture instance.

        Verifies that check_azure_openai returns WARN status when
        the Azure OpenAI API connection fails with a network error.
        """
        with patch('openai.AzureOpenAI') as mock_client:
            mock_client.return_value.chat.completions.create.side_effect = ConnectionError("timeout")
            
            result = checker.check_azure_openai()
            
            assert result.status == CheckStatus.WARN
            assert "ConnectionError" in result.message
    
    # Folder access checks
    @patch('src.utils.startup_checks.PROJECTS_DIR', Path('/tmp/test_projects'))
    @patch('src.utils.startup_checks.BASE_DIR', Path('/tmp/test_base'))
    @patch('src.utils.startup_checks.GITHUB_ENABLED', False)
    def test_check_folder_access_success(self, checker, tmp_path):
        """Test folder access check when successful.

        Args:
            checker: The StartupChecker fixture instance.
            tmp_path: Pytest fixture providing a temporary directory.

        Verifies that check_folder_access returns PASS status when
        all required directories are accessible and writable.
        """
        projects_dir = tmp_path / "projects"
        base_dir = tmp_path
        config_path = base_dir / "config.yaml"
        config_path.write_text("test: true")
        
        with patch('src.utils.startup_checks.PROJECTS_DIR', projects_dir):
            with patch('src.utils.startup_checks.BASE_DIR', base_dir):
                result = checker.check_folder_access()
        
        assert result.status == CheckStatus.PASS
    
    @patch('src.utils.startup_checks.GITHUB_ENABLED', False)
    def test_check_folder_access_missing_config(self, checker, tmp_path):
        """Test folder access check when config.yaml is missing.

        Args:
            checker: The StartupChecker fixture instance.
            tmp_path: Pytest fixture providing a temporary directory.

        Verifies that check_folder_access returns WARN or FAIL status
        when the config.yaml file is not found in the base directory.
        """
        projects_dir = tmp_path / "projects"
        base_dir = tmp_path / "nonexistent"
        
        with patch('src.utils.startup_checks.PROJECTS_DIR', projects_dir):
            with patch('src.utils.startup_checks.BASE_DIR', base_dir):
                result = checker.check_folder_access()
        
        assert result.status in [CheckStatus.WARN, CheckStatus.FAIL]
        assert "config.yaml" in result.details
    
    @patch('src.utils.startup_checks.GITHUB_ENABLED', True)
    def test_check_folder_access_missing_gitignore(self, checker, tmp_path):
        """Test folder access check when .gitignore is missing for GitHub.

        Args:
            checker: The StartupChecker fixture instance.
            tmp_path: Pytest fixture providing a temporary directory.

        Verifies that check_folder_access returns WARN status when
        GitHub is enabled but .gitignore file is missing.
        """
        projects_dir = tmp_path / "projects"
        base_dir = tmp_path
        config_path = base_dir / "config.yaml"
        config_path.write_text("test: true")
        
        with patch('src.utils.startup_checks.PROJECTS_DIR', projects_dir):
            with patch('src.utils.startup_checks.BASE_DIR', base_dir):
                result = checker.check_folder_access()
        
        assert result.status == CheckStatus.WARN
        assert ".gitignore" in result.details
    
    @patch('src.utils.startup_checks.GITHUB_ENABLED', False)
    def test_check_folder_access_permission_error(self, checker, tmp_path):
        """Test folder access check with permission error during write.

        Args:
            checker: The StartupChecker fixture instance.
            tmp_path: Pytest fixture providing a temporary directory.

        Verifies that check_folder_access returns WARN or FAIL status
        when a permission error occurs while testing write access.
        """
        projects_dir = tmp_path / "projects"
        base_dir = tmp_path
        config_path = base_dir / "config.yaml"
        config_path.write_text("test: true")
        
        with patch('src.utils.startup_checks.PROJECTS_DIR', projects_dir):
            with patch('src.utils.startup_checks.BASE_DIR', base_dir):
                with patch.object(Path, 'write_text', side_effect=PermissionError("Access denied")):
                    result = checker.check_folder_access()
        
        assert result.status in [CheckStatus.WARN, CheckStatus.FAIL]
    
    # Copilot CLI checks
    def test_check_copilot_cli_success(self, checker):
        """Test Copilot CLI check when available.

        Args:
            checker: The StartupChecker fixture instance.

        Verifies that check_copilot_cli returns PASS status when
        the Copilot CLI command executes successfully.
        """
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="GitHub Copilot CLI v1.0.0"
            )
            
            result = checker.check_copilot_cli()
            
            assert result.status == CheckStatus.PASS
            assert "Available" in result.message
    
    def test_check_copilot_cli_not_found(self, checker):
        """Test Copilot CLI check when not found.

        Args:
            checker: The StartupChecker fixture instance.

        Verifies that check_copilot_cli returns FAIL status when
        the Copilot CLI executable is not found on the system.
        """
        with patch('subprocess.run', side_effect=FileNotFoundError()):
            result = checker.check_copilot_cli()
            
            assert result.status == CheckStatus.FAIL
            assert "not found" in result.message.lower()
    
    def test_check_copilot_cli_timeout(self, checker):
        """Test Copilot CLI check when timeout occurs.

        Args:
            checker: The StartupChecker fixture instance.

        Verifies that check_copilot_cli returns WARN status when
        the command times out during execution.
        """
        with patch('subprocess.run', side_effect=subprocess.TimeoutExpired("copilot", 10)):
            result = checker.check_copilot_cli()
            
            assert result.status == CheckStatus.WARN
            assert "Timeout" in result.message
    
    def test_check_copilot_cli_error_return_code(self, checker):
        """Test Copilot CLI check when command returns error.

        Args:
            checker: The StartupChecker fixture instance.

        Verifies that check_copilot_cli returns FAIL status when
        the command exits with a non-zero return code.
        """
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="")
            
            result = checker.check_copilot_cli()
            
            assert result.status == CheckStatus.FAIL
            assert "not installed" in result.message.lower()
    
    def test_check_copilot_cli_generic_exception(self, checker):
        """Test Copilot CLI check with generic exception.

        Args:
            checker: The StartupChecker fixture instance.

        Verifies that check_copilot_cli returns FAIL status and
        includes the exception type when an unexpected error occurs.
        """
        with patch('subprocess.run', side_effect=RuntimeError("Unknown error")):
            result = checker.check_copilot_cli()
            
            assert result.status == CheckStatus.FAIL
            assert "RuntimeError" in result.message
    
    # Git checks
    def test_check_git_success(self, checker):
        """Test Git check when available.

        Args:
            checker: The StartupChecker fixture instance.

        Verifies that check_git returns PASS status when the git
        command executes successfully and returns version info.
        """
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="git version 2.40.0"
            )
            
            result = checker.check_git()
            
            assert result.status == CheckStatus.PASS
            assert "git version" in result.message
    
    def test_check_git_not_found(self, checker):
        """Test Git check when not found.

        Args:
            checker: The StartupChecker fixture instance.

        Verifies that check_git returns FAIL status when the git
        executable is not found on the system.
        """
        with patch('subprocess.run', side_effect=FileNotFoundError()):
            result = checker.check_git()
            
            assert result.status == CheckStatus.FAIL
            assert "not found" in result.message.lower()
    
    def test_check_git_error_return_code(self, checker):
        """Test Git check when command returns error.

        Args:
            checker: The StartupChecker fixture instance.

        Verifies that check_git returns FAIL status when the git
        command exits with a non-zero return code.
        """
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="")
            
            result = checker.check_git()
            
            assert result.status == CheckStatus.FAIL
    
    def test_check_git_generic_exception(self, checker):
        """Test Git check with generic exception.

        Args:
            checker: The StartupChecker fixture instance.

        Verifies that check_git returns FAIL status and includes the
        exception type when an unexpected error occurs.
        """
        with patch('subprocess.run', side_effect=RuntimeError("Unknown error")):
            result = checker.check_git()
            
            assert result.status == CheckStatus.FAIL
            assert "RuntimeError" in result.message
    
    # Run all checks
    @patch('src.utils.startup_checks.DISCORD_BOT_TOKEN', 'a' * 60)
    @patch('src.utils.startup_checks.GITHUB_ENABLED', False)
    @patch('src.utils.startup_checks.AZURE_OPENAI_ENDPOINT', None)
    @patch('src.utils.startup_checks.AZURE_OPENAI_API_KEY', None)
    @patch('src.utils.startup_checks.AZURE_OPENAI_DEPLOYMENT_NAME', None)
    def test_run_all_checks(self, checker, tmp_path):
        """Test running all checks.

        Args:
            checker: The StartupChecker fixture instance.
            tmp_path: Pytest fixture providing a temporary directory.

        Verifies that run_all_checks executes all 6 startup checks
        and returns a list of CheckResult objects.
        """
        projects_dir = tmp_path / "projects"
        base_dir = tmp_path
        config_path = base_dir / "config.yaml"
        config_path.write_text("test: true")
        
        with patch('src.utils.startup_checks.PROJECTS_DIR', projects_dir):
            with patch('src.utils.startup_checks.BASE_DIR', base_dir):
                with patch('subprocess.run') as mock_run:
                    mock_run.return_value = MagicMock(returncode=0, stdout="version")
                    
                    results = checker.run_all_checks()
        
        assert len(results) == 6
        assert all(isinstance(r, CheckResult) for r in results)
    
    def test_run_all_checks_with_exception(self, checker):
        """Test run_all_checks handles exceptions in checks.

        Args:
            checker: The StartupChecker fixture instance.

        Verifies that run_all_checks continues executing remaining checks
        even when one check raises an exception, recording the failure.
        """
        # The first check (discord_token) will raise, the rest will proceed normally
        original_check_discord = checker.check_discord_token
        
        def mock_discord_token():
            raise RuntimeError("Test error")
        
        # Replace only the discord token check
        checker.check_discord_token = mock_discord_token
        
        # Mock the other checks to be simple passes by patching the config values
        with patch('src.utils.startup_checks.GITHUB_ENABLED', False):
            with patch('src.utils.startup_checks.AZURE_OPENAI_ENDPOINT', None):
                with patch('src.utils.startup_checks.AZURE_OPENAI_API_KEY', None):
                    with patch('src.utils.startup_checks.AZURE_OPENAI_DEPLOYMENT_NAME', None):
                        with patch('subprocess.run') as mock_run:
                            mock_run.return_value = MagicMock(returncode=0, stdout="version")
                            with patch('src.utils.startup_checks.PROJECTS_DIR', Path('/tmp/test')):
                                with patch('src.utils.startup_checks.BASE_DIR', Path('/tmp')):
                                    with patch.object(Path, 'mkdir'):
                                        with patch.object(Path, 'exists', return_value=True):
                                            with patch.object(Path, 'read_text', return_value='test'):
                                                with patch.object(Path, 'write_text'):
                                                    with patch.object(Path, 'unlink'):
                                                        results = checker.run_all_checks()
        
        # Should have 6 results
        assert len(results) == 6
        # First check (Discord Bot Token) should have failed due to exception
        assert results[0].status == CheckStatus.FAIL
        assert "RuntimeError" in results[0].message
    
    # Log result
    def test_log_result_pass(self, checker):
        """Test logging a PASS result.

        Args:
            checker: The StartupChecker fixture instance.

        Verifies that _log_result handles PASS status without raising.
        """
        result = CheckResult(name="Test", status=CheckStatus.PASS, message="OK")
        checker._log_result(result)  # Should not raise
    
    def test_log_result_warn_with_details(self, checker):
        """Test logging a WARN result with details.

        Args:
            checker: The StartupChecker fixture instance.

        Verifies that _log_result handles WARN status with details.
        """
        result = CheckResult(
            name="Test",
            status=CheckStatus.WARN,
            message="Warning",
            details="Some details"
        )
        checker._log_result(result)  # Should not raise
    
    def test_log_result_fail_with_details(self, checker):
        """Test logging a FAIL result with details.

        Args:
            checker: The StartupChecker fixture instance.

        Verifies that _log_result handles FAIL status with details.
        """
        result = CheckResult(
            name="Test",
            status=CheckStatus.FAIL,
            message="Failed",
            details="Error details"
        )
        checker._log_result(result)  # Should not raise
    
    def test_log_result_skip_with_details(self, checker):
        """Test logging a SKIP result with details.

        Args:
            checker: The StartupChecker fixture instance.

        Verifies that _log_result handles SKIP status with details.
        """
        result = CheckResult(
            name="Test",
            status=CheckStatus.SKIP,
            message="Skipped",
            details="Why skipped"
        )
        checker._log_result(result)  # Should not raise
    
    # Has critical failures
    def test_has_critical_failures_false(self, checker):
        """Test has_critical_failures returns False when no critical failures.

        Args:
            checker: The StartupChecker fixture instance.

        Verifies that has_critical_failures returns False when all
        critical checks (Discord, Folder, Copilot) pass.
        """
        checker.results = [
            CheckResult(name="Discord Bot Token", status=CheckStatus.PASS, message="OK"),
            CheckResult(name="Folder Access", status=CheckStatus.PASS, message="OK"),
            CheckResult(name="Copilot CLI", status=CheckStatus.PASS, message="OK"),
        ]
        
        assert not checker.has_critical_failures()
    
    def test_has_critical_failures_true_discord(self, checker):
        """Test has_critical_failures returns True when Discord token fails.

        Args:
            checker: The StartupChecker fixture instance.

        Verifies that has_critical_failures returns True when the
        Discord Bot Token check has FAIL status.
        """
        checker.results = [
            CheckResult(name="Discord Bot Token", status=CheckStatus.FAIL, message="Missing"),
        ]
        
        assert checker.has_critical_failures()
    
    def test_has_critical_failures_true_folder(self, checker):
        """Test has_critical_failures returns True when folder access fails.

        Args:
            checker: The StartupChecker fixture instance.

        Verifies that has_critical_failures returns True when the
        Folder Access check has FAIL status.
        """
        checker.results = [
            CheckResult(name="Folder Access", status=CheckStatus.FAIL, message="No access"),
        ]
        
        assert checker.has_critical_failures()
    
    def test_has_critical_failures_true_copilot(self, checker):
        """Test has_critical_failures returns True when Copilot CLI fails.

        Args:
            checker: The StartupChecker fixture instance.

        Verifies that has_critical_failures returns True when the
        Copilot CLI check has FAIL status.
        """
        checker.results = [
            CheckResult(name="Copilot CLI", status=CheckStatus.FAIL, message="Not found"),
        ]
        
        assert checker.has_critical_failures()
    
    def test_has_critical_failures_false_non_critical(self, checker):
        """Test has_critical_failures returns False for non-critical failures.

        Args:
            checker: The StartupChecker fixture instance.

        Verifies that has_critical_failures returns False when only
        non-critical checks (GitHub, Azure) have FAIL status.
        """
        checker.results = [
            CheckResult(name="GitHub Integration", status=CheckStatus.FAIL, message="Bad token"),
            CheckResult(name="Azure OpenAI", status=CheckStatus.FAIL, message="Connection error"),
        ]
        
        assert not checker.has_critical_failures()
    
    # Get failures/warnings
    def test_get_failures(self, checker):
        """Test get_failures returns only failed results.

        Args:
            checker: The StartupChecker fixture instance.

        Verifies that get_failures returns a list containing only
        CheckResult objects with FAIL status.
        """
        checker.results = [
            CheckResult(name="Test1", status=CheckStatus.PASS, message="OK"),
            CheckResult(name="Test2", status=CheckStatus.FAIL, message="Failed"),
            CheckResult(name="Test3", status=CheckStatus.WARN, message="Warning"),
        ]
        
        failures = checker.get_failures()
        assert len(failures) == 1
        assert failures[0].name == "Test2"
    
    def test_get_warnings(self, checker):
        """Test get_warnings returns only warning results.

        Args:
            checker: The StartupChecker fixture instance.

        Verifies that get_warnings returns a list containing only
        CheckResult objects with WARN status.
        """
        checker.results = [
            CheckResult(name="Test1", status=CheckStatus.PASS, message="OK"),
            CheckResult(name="Test2", status=CheckStatus.FAIL, message="Failed"),
            CheckResult(name="Test3", status=CheckStatus.WARN, message="Warning"),
        ]
        
        warnings = checker.get_warnings()
        assert len(warnings) == 1
        assert warnings[0].name == "Test3"


class TestRunStartupChecks:
    """Tests for run_startup_checks function."""
    
    @patch('src.utils.startup_checks.DISCORD_BOT_TOKEN', 'a' * 60)
    @patch('src.utils.startup_checks.GITHUB_ENABLED', False)
    @patch('src.utils.startup_checks.AZURE_OPENAI_ENDPOINT', None)
    @patch('src.utils.startup_checks.AZURE_OPENAI_API_KEY', None)
    @patch('src.utils.startup_checks.AZURE_OPENAI_DEPLOYMENT_NAME', None)
    def test_run_startup_checks_success(self, tmp_path):
        """Test run_startup_checks when all critical checks pass.

        Args:
            tmp_path: Pytest fixture providing a temporary directory.

        Verifies that run_startup_checks returns a StartupChecker
        instance with no critical failures when all checks pass.
        """
        projects_dir = tmp_path / "projects"
        base_dir = tmp_path
        config_path = base_dir / "config.yaml"
        config_path.write_text("test: true")
        
        with patch('src.utils.startup_checks.PROJECTS_DIR', projects_dir):
            with patch('src.utils.startup_checks.BASE_DIR', base_dir):
                with patch('subprocess.run') as mock_run:
                    mock_run.return_value = MagicMock(returncode=0, stdout="version")
                    
                    checker = run_startup_checks(exit_on_critical=True)
        
        assert isinstance(checker, StartupChecker)
        assert not checker.has_critical_failures()
    
    @patch('src.utils.startup_checks.DISCORD_BOT_TOKEN', None)
    def test_run_startup_checks_exit_on_critical(self):
        """Test run_startup_checks raises SystemExit on critical failure.

        Verifies that run_startup_checks raises SystemExit with an
        informative message when a critical check fails and
        exit_on_critical is True.
        """
        with patch('src.utils.startup_checks.StartupChecker.run_all_checks'):
            with patch('src.utils.startup_checks.StartupChecker.has_critical_failures', return_value=True):
                with patch('src.utils.startup_checks.StartupChecker.get_failures') as mock_failures:
                    mock_failures.return_value = [
                        CheckResult(name="Discord Bot Token", status=CheckStatus.FAIL, message="Missing")
                    ]
                    
                    with pytest.raises(SystemExit) as exc_info:
                        run_startup_checks(exit_on_critical=True)
                    
                    assert "Discord Bot Token" in str(exc_info.value)
    
    @patch('src.utils.startup_checks.DISCORD_BOT_TOKEN', None)
    def test_run_startup_checks_no_exit(self):
        """Test run_startup_checks doesn't exit when exit_on_critical is False.

        Verifies that run_startup_checks returns a StartupChecker
        instance without raising SystemExit when exit_on_critical
        is set to False, even with critical failures.
        """
        with patch('src.utils.startup_checks.StartupChecker.run_all_checks'):
            with patch('src.utils.startup_checks.StartupChecker.has_critical_failures', return_value=True):
                # Should not raise even with critical failures
                checker = run_startup_checks(exit_on_critical=False)
                assert isinstance(checker, StartupChecker)
