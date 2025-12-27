"""
GitHub utility module for repository creation and management.

This module provides functionality to:
- Create new GitHub repositories
- Initialize local git repositories
- Push project files to GitHub
- Copy .gitignore files to projects
"""

import subprocess
import shutil
from pathlib import Path
from typing import Optional, Tuple

from github import Github, GithubException

from ..config import (
    GITHUB_TOKEN,
    GITHUB_USERNAME,
    BASE_DIR,
    GITHUB_ENABLED
)
from .logging import logger


class GitHubManager:
    """Manages GitHub repository operations."""
    
    def __init__(self):
        """Initialize the GitHub manager with credentials from config."""
        self.enabled = GITHUB_ENABLED
        self.token = GITHUB_TOKEN
        self.username = GITHUB_USERNAME
        self._github: Optional[Github] = None
    
    @property
    def github(self) -> Optional[Github]:
        """Lazy-load the GitHub client."""
        if not self.enabled:
            return None
        if self._github is None and self.token:
            self._github = Github(self.token)
        return self._github
    
    def is_configured(self) -> bool:
        """Check if GitHub integration is properly configured."""
        return bool(self.enabled and self.token and self.username)
    
    def copy_gitignore(self, project_path: Path) -> bool:
        """
        Copy the root .gitignore to the project directory.
        
        Args:
            project_path: Path to the project directory
            
        Returns:
            True if successful, False otherwise
        """
        source_gitignore = BASE_DIR / ".gitignore"
        dest_gitignore = project_path / ".gitignore"
        
        try:
            if source_gitignore.exists():
                shutil.copy2(source_gitignore, dest_gitignore)
                logger.info(f"Copied .gitignore to {project_path}")
                return True
            else:
                logger.warning(f"Source .gitignore not found at {source_gitignore}")
                return False
        except Exception as e:
            logger.error(f"Failed to copy .gitignore: {e}")
            return False
    
    def create_repository(
        self,
        repo_name: str,
        description: str = "",
        private: bool = False
    ) -> Tuple[bool, str, Optional[str]]:
        """
        Create a new GitHub repository.
        
        Args:
            repo_name: Name for the new repository
            description: Repository description
            private: Whether the repository should be private
            
        Returns:
            Tuple of (success, message, clone_url)
        """
        if not self.is_configured():
            return False, "GitHub integration not configured", None
        
        try:
            user = self.github.get_user()
            repo = user.create_repo(
                name=repo_name,
                description=description,
                private=private,
                auto_init=False  # We'll push our own content
            )
            logger.info(f"Created GitHub repository: {repo.full_name}")
            return True, f"Repository created: {repo.html_url}", repo.clone_url
        except GithubException as e:
            error_msg = f"GitHub API error: {e.data.get('message', str(e))}"
            logger.error(error_msg)
            return False, error_msg, None
        except Exception as e:
            error_msg = f"Failed to create repository: {e}"
            logger.error(error_msg)
            return False, error_msg, None
    
    def init_and_push(
        self,
        project_path: Path,
        repo_name: str,
        commit_message: str = "Initial commit from Discord Copilot Bot"
    ) -> Tuple[bool, str]:
        """
        Initialize a git repository and push to GitHub.
        
        Args:
            project_path: Path to the project directory
            repo_name: Name of the GitHub repository
            commit_message: Commit message for initial commit
            
        Returns:
            Tuple of (success, message)
        """
        if not self.is_configured():
            return False, "GitHub integration not configured"
        
        try:
            # Get the authenticated user's info from GitHub API
            user = self.github.get_user()
            git_name = user.name or user.login
            git_email = user.email or f"{user.login}@users.noreply.github.com"
            
            logger.info(f"Using git identity: {git_name} <{git_email}>")
            
            # Build the authenticated remote URL
            remote_url = f"https://{user.login}:{self.token}@github.com/{user.login}/{repo_name}.git"
            
            # Git commands to execute - configure user before commit
            git_commands = [
                ["git", "init"],
                ["git", "config", "user.name", git_name],
                ["git", "config", "user.email", git_email],
                ["git", "add", "."],
                ["git", "commit", "-m", commit_message],
                ["git", "branch", "-M", "main"],
                ["git", "remote", "add", "origin", remote_url],
                ["git", "push", "-u", "origin", "main"]
            ]
            
            for cmd in git_commands:
                result = subprocess.run(
                    cmd,
                    cwd=str(project_path),
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                if result.returncode != 0:
                    # Don't log the full command as it may contain the token
                    safe_cmd = cmd[0:2] if cmd[0] == "git" else cmd
                    error_msg = f"Git command failed: {' '.join(safe_cmd)}: {result.stderr}"
                    logger.error(error_msg)
                    return False, error_msg
            
            public_url = f"https://github.com/{user.login}/{repo_name}"
            logger.info(f"Successfully pushed to GitHub: {public_url}")
            return True, f"Pushed to GitHub: {public_url}"
            
        except subprocess.TimeoutExpired:
            error_msg = "Git operation timed out"
            logger.error(error_msg)
            return False, error_msg
        except Exception as e:
            error_msg = f"Failed to push to GitHub: {e}"
            logger.error(error_msg)
            return False, error_msg
    
    def create_and_push_project(
        self,
        project_path: Path,
        repo_name: str,
        description: str = "",
        private: bool = False
    ) -> Tuple[bool, str, Optional[str]]:
        """
        Complete workflow: copy .gitignore, create repo, init git, and push.
        
        Args:
            project_path: Path to the project directory
            repo_name: Name for the GitHub repository
            description: Repository description
            private: Whether the repository should be private
            
        Returns:
            Tuple of (success, message, github_url)
        """
        if not self.is_configured():
            return False, "GitHub integration not configured. Set GITHUB_TOKEN and GITHUB_USERNAME in .env", None
        
        # Get the authenticated user's login
        try:
            user = self.github.get_user()
            user_login = user.login
        except Exception as e:
            return False, f"Failed to get GitHub user info: {e}", None
        
        # Step 1: Copy .gitignore
        self.copy_gitignore(project_path)
        
        # Step 2: Create the repository
        success, message, clone_url = self.create_repository(
            repo_name=repo_name,
            description=description,
            private=private
        )
        if not success:
            return False, message, None
        
        # Step 3: Initialize and push
        success, push_message = self.init_and_push(project_path, repo_name)
        if not success:
            return False, push_message, None
        
        github_url = f"https://github.com/{user_login}/{repo_name}"
        return True, f"Project pushed to GitHub: {github_url}", github_url


# Singleton instance for easy access
github_manager = GitHubManager()
