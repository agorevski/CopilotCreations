"""
Startup checks module for validating all integrations and functionality.

This module provides comprehensive validation of:
- Discord bot token and permissions
- GitHub API configuration and connectivity
- Azure OpenAI configuration and connectivity
- Folder access and write permissions
- Required dependencies and tools
"""

import os
import shutil
import subprocess
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import List, Optional

from ..config import (
    DISCORD_BOT_TOKEN,
    GITHUB_ENABLED,
    GITHUB_TOKEN,
    GITHUB_USERNAME,
    AZURE_OPENAI_ENDPOINT,
    AZURE_OPENAI_API_KEY,
    AZURE_OPENAI_DEPLOYMENT_NAME,
    PROJECTS_DIR,
    BASE_DIR,
)
from .logging import logger


class CheckStatus(Enum):
    """Status of a startup check."""
    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"
    SKIP = "SKIP"


@dataclass
class CheckResult:
    """Result of a single startup check."""
    name: str
    status: CheckStatus
    message: str
    details: Optional[str] = None


class StartupChecker:
    """Performs startup checks to validate all integrations and functionality."""
    
    def __init__(self):
        """Initialize the startup checker."""
        self.results: List[CheckResult] = []
    
    def _add_result(
        self,
        name: str,
        status: CheckStatus,
        message: str,
        details: Optional[str] = None
    ) -> CheckResult:
        """Add a check result to the results list."""
        result = CheckResult(name=name, status=status, message=message, details=details)
        self.results.append(result)
        return result
    
    def check_discord_token(self) -> CheckResult:
        """Check if Discord bot token is configured."""
        if not DISCORD_BOT_TOKEN:
            return self._add_result(
                name="Discord Bot Token",
                status=CheckStatus.FAIL,
                message="DISCORD_BOT_TOKEN environment variable is not set",
                details="Set DISCORD_BOT_TOKEN in your .env file"
            )
        
        # Basic token format validation (Discord tokens have a specific format)
        if len(DISCORD_BOT_TOKEN) < 50:
            return self._add_result(
                name="Discord Bot Token",
                status=CheckStatus.WARN,
                message="Discord token seems unusually short",
                details="Token may be invalid - verify in Discord Developer Portal"
            )
        
        return self._add_result(
            name="Discord Bot Token",
            status=CheckStatus.PASS,
            message="Discord bot token is configured"
        )
    
    def check_github_integration(self) -> CheckResult:
        """Check GitHub integration configuration and connectivity."""
        if not GITHUB_ENABLED:
            return self._add_result(
                name="GitHub Integration",
                status=CheckStatus.SKIP,
                message="GitHub integration is disabled",
                details="Set GITHUB_ENABLED=true in .env to enable"
            )
        
        # Check required credentials
        missing = []
        if not GITHUB_TOKEN:
            missing.append("GITHUB_TOKEN")
        if not GITHUB_USERNAME:
            missing.append("GITHUB_USERNAME")
        
        if missing:
            return self._add_result(
                name="GitHub Integration",
                status=CheckStatus.FAIL,
                message=f"Missing required environment variables: {', '.join(missing)}",
                details="Set these variables in your .env file"
            )
        
        # Test GitHub API connectivity
        try:
            from github import Github, GithubException
            
            gh = Github(GITHUB_TOKEN)
            user = gh.get_user()
            authenticated_user = user.login
            
            # Verify the username matches
            if authenticated_user.lower() != GITHUB_USERNAME.lower():
                return self._add_result(
                    name="GitHub Integration",
                    status=CheckStatus.WARN,
                    message=f"Authenticated as '{authenticated_user}' but GITHUB_USERNAME is '{GITHUB_USERNAME}'",
                    details="This may cause issues with repository creation"
                )
            
            return self._add_result(
                name="GitHub Integration",
                status=CheckStatus.PASS,
                message=f"Connected as '{authenticated_user}'"
            )
            
        except GithubException as e:
            return self._add_result(
                name="GitHub Integration",
                status=CheckStatus.FAIL,
                message=f"GitHub API error: {e.data.get('message', str(e)) if hasattr(e, 'data') else str(e)}",
                details="Check your GITHUB_TOKEN has the required 'repo' scope"
            )
        except Exception as e:
            return self._add_result(
                name="GitHub Integration",
                status=CheckStatus.FAIL,
                message=f"Failed to connect to GitHub: {type(e).__name__}: {e}"
            )
    
    def check_azure_openai(self) -> CheckResult:
        """Check Azure OpenAI configuration and connectivity."""
        # Check if any Azure OpenAI config is set
        has_any_config = any([
            AZURE_OPENAI_ENDPOINT,
            AZURE_OPENAI_API_KEY,
            AZURE_OPENAI_DEPLOYMENT_NAME
        ])
        
        if not has_any_config:
            return self._add_result(
                name="Azure OpenAI",
                status=CheckStatus.SKIP,
                message="Azure OpenAI is not configured",
                details="Optional - used for creative repository naming"
            )
        
        # Check all required config is present
        missing = []
        if not AZURE_OPENAI_ENDPOINT:
            missing.append("AZURE_OPENAI_ENDPOINT")
        if not AZURE_OPENAI_API_KEY:
            missing.append("AZURE_OPENAI_API_KEY")
        if not AZURE_OPENAI_DEPLOYMENT_NAME:
            missing.append("AZURE_OPENAI_DEPLOYMENT_NAME")
        
        if missing:
            return self._add_result(
                name="Azure OpenAI",
                status=CheckStatus.WARN,
                message=f"Incomplete configuration - missing: {', '.join(missing)}",
                details="Repository naming will fall back to timestamps"
            )
        
        # Test Azure OpenAI connectivity
        try:
            from openai import AzureOpenAI
            
            client = AzureOpenAI(
                azure_endpoint=AZURE_OPENAI_ENDPOINT,
                api_key=AZURE_OPENAI_API_KEY,
                api_version="2025-01-01-preview"
            )
            
            # Make a minimal test request
            response = client.chat.completions.create(
                model=AZURE_OPENAI_DEPLOYMENT_NAME,
                messages=[{"role": "user", "content": "test"}],
                max_completion_tokens=5
            )
            
            return self._add_result(
                name="Azure OpenAI",
                status=CheckStatus.PASS,
                message=f"Connected to deployment '{AZURE_OPENAI_DEPLOYMENT_NAME}'"
            )
            
        except Exception as e:
            return self._add_result(
                name="Azure OpenAI",
                status=CheckStatus.WARN,
                message=f"Could not verify Azure OpenAI connectivity: {type(e).__name__}",
                details="Repository naming may fall back to timestamps"
            )
    
    def check_folder_access(self) -> CheckResult:
        """Check folder access and write permissions."""
        issues = []
        
        # Check projects directory
        try:
            PROJECTS_DIR.mkdir(exist_ok=True)
            
            # Test write access by creating a temp file
            test_file = PROJECTS_DIR / ".startup_check_test"
            try:
                test_file.write_text("test")
                test_file.unlink()
            except PermissionError:
                issues.append(f"No write access to {PROJECTS_DIR}")
            except Exception as e:
                issues.append(f"Error testing write access: {e}")
                
        except PermissionError:
            issues.append(f"Cannot create projects directory: {PROJECTS_DIR}")
        except Exception as e:
            issues.append(f"Error with projects directory: {e}")
        
        # Check config.yaml exists and is readable
        config_path = BASE_DIR / "config.yaml"
        if not config_path.exists():
            issues.append("config.yaml not found")
        else:
            try:
                config_path.read_text()
            except PermissionError:
                issues.append("Cannot read config.yaml")
        
        # Check .gitignore exists (for GitHub integration)
        gitignore_path = BASE_DIR / ".gitignore"
        if GITHUB_ENABLED and not gitignore_path.exists():
            issues.append(".gitignore not found (needed for GitHub integration)")
        
        if issues:
            return self._add_result(
                name="Folder Access",
                status=CheckStatus.FAIL if "No write access" in str(issues) else CheckStatus.WARN,
                message=f"Found {len(issues)} issue(s)",
                details="; ".join(issues)
            )
        
        return self._add_result(
            name="Folder Access",
            status=CheckStatus.PASS,
            message=f"Projects directory: {PROJECTS_DIR}"
        )
    
    def check_copilot_cli(self) -> CheckResult:
        """Check if Copilot CLI (copilot.exe) is available."""
        try:
            # Check if copilot CLI is installed
            result = subprocess.run(
                ["copilot", "--version"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode != 0:
                return self._add_result(
                    name="Copilot CLI",
                    status=CheckStatus.FAIL,
                    message="Copilot CLI is not installed or not in PATH",
                    details="Ensure copilot.exe is installed and accessible"
                )
            
            version_info = result.stdout.strip() if result.stdout else "unknown"
            
            return self._add_result(
                name="Copilot CLI",
                status=CheckStatus.PASS,
                message=f"Available ({version_info})"
            )
            
        except FileNotFoundError:
            return self._add_result(
                name="Copilot CLI",
                status=CheckStatus.FAIL,
                message="Copilot CLI (copilot.exe) not found in PATH",
                details="Ensure copilot.exe is installed and accessible"
            )
        except subprocess.TimeoutExpired:
            return self._add_result(
                name="Copilot CLI",
                status=CheckStatus.WARN,
                message="Timeout checking Copilot CLI",
                details="CLI may be slow or unresponsive"
            )
        except Exception as e:
            return self._add_result(
                name="Copilot CLI",
                status=CheckStatus.FAIL,
                message=f"Error checking Copilot CLI: {type(e).__name__}: {e}"
            )
    
    def check_git(self) -> CheckResult:
        """Check if Git is installed and configured."""
        try:
            result = subprocess.run(
                ["git", "--version"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode != 0:
                return self._add_result(
                    name="Git",
                    status=CheckStatus.FAIL,
                    message="Git is not installed or not in PATH"
                )
            
            git_version = result.stdout.strip() if result.stdout else "unknown"
            
            return self._add_result(
                name="Git",
                status=CheckStatus.PASS,
                message=git_version
            )
            
        except FileNotFoundError:
            return self._add_result(
                name="Git",
                status=CheckStatus.FAIL,
                message="Git not found in PATH",
                details="Install Git from https://git-scm.com/"
            )
        except Exception as e:
            return self._add_result(
                name="Git",
                status=CheckStatus.FAIL,
                message=f"Error checking Git: {type(e).__name__}: {e}"
            )
    
    def run_all_checks(self) -> List[CheckResult]:
        """Run all startup checks and return results."""
        self.results = []  # Reset results
        
        logger.info("=" * 60)
        logger.info("STARTUP CHECKS")
        logger.info("=" * 60)
        
        # Run all checks
        checks = [
            ("Discord Bot Token", self.check_discord_token),
            ("Folder Access", self.check_folder_access),
            ("Git", self.check_git),
            ("Copilot CLI", self.check_copilot_cli),
            ("GitHub Integration", self.check_github_integration),
            ("Azure OpenAI", self.check_azure_openai),
        ]
        
        for name, check_func in checks:
            try:
                result = check_func()
                self._log_result(result)
            except Exception as e:
                result = self._add_result(
                    name=name,
                    status=CheckStatus.FAIL,
                    message=f"Check failed with error: {type(e).__name__}: {e}"
                )
                self._log_result(result)
        
        # Summary
        logger.info("-" * 60)
        passed = sum(1 for r in self.results if r.status == CheckStatus.PASS)
        warned = sum(1 for r in self.results if r.status == CheckStatus.WARN)
        failed = sum(1 for r in self.results if r.status == CheckStatus.FAIL)
        skipped = sum(1 for r in self.results if r.status == CheckStatus.SKIP)
        
        summary = f"Results: {passed} passed"
        if warned:
            summary += f", {warned} warnings"
        if failed:
            summary += f", {failed} failed"
        if skipped:
            summary += f", {skipped} skipped"
        
        logger.info(summary)
        logger.info("=" * 60)
        
        return self.results
    
    def _log_result(self, result: CheckResult) -> None:
        """Log a check result with appropriate formatting."""
        status_icons = {
            CheckStatus.PASS: "✓",
            CheckStatus.WARN: "⚠",
            CheckStatus.FAIL: "✗",
            CheckStatus.SKIP: "○",
        }
        
        icon = status_icons.get(result.status, "?")
        log_msg = f"[{icon}] {result.name}: {result.message}"
        
        if result.status == CheckStatus.PASS:
            logger.info(log_msg)
        elif result.status == CheckStatus.WARN:
            logger.warning(log_msg)
            if result.details:
                logger.warning(f"    └─ {result.details}")
        elif result.status == CheckStatus.FAIL:
            logger.error(log_msg)
            if result.details:
                logger.error(f"    └─ {result.details}")
        else:  # SKIP
            logger.info(log_msg)
            if result.details:
                logger.info(f"    └─ {result.details}")
    
    def has_critical_failures(self) -> bool:
        """Check if any critical checks failed (Discord token, folder access)."""
        critical_checks = ["Discord Bot Token", "Folder Access", "Copilot CLI"]
        for result in self.results:
            if result.name in critical_checks and result.status == CheckStatus.FAIL:
                return True
        return False
    
    def get_failures(self) -> List[CheckResult]:
        """Get all failed check results."""
        return [r for r in self.results if r.status == CheckStatus.FAIL]
    
    def get_warnings(self) -> List[CheckResult]:
        """Get all warning check results."""
        return [r for r in self.results if r.status == CheckStatus.WARN]


def run_startup_checks(exit_on_critical: bool = True) -> StartupChecker:
    """Run all startup checks and optionally exit on critical failures.
    
    Args:
        exit_on_critical: If True, raise an exception on critical failures.
        
    Returns:
        The StartupChecker instance with results.
        
    Raises:
        SystemExit: If exit_on_critical is True and critical checks fail.
    """
    checker = StartupChecker()
    checker.run_all_checks()
    
    if exit_on_critical and checker.has_critical_failures():
        failures = checker.get_failures()
        failure_names = [f.name for f in failures]
        raise SystemExit(
            f"Critical startup checks failed: {', '.join(failure_names)}. "
            "Please fix these issues before starting the bot."
        )
    
    return checker
