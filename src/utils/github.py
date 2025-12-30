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
from typing import Optional, Tuple, Protocol

from github import Github, GithubException

from ..config import (
    GITHUB_TOKEN,
    GITHUB_USERNAME,
    BASE_DIR,
    GITHUB_ENABLED
)
from .logging import logger


# Discord error codes
DISCORD_INVALID_WEBHOOK_TOKEN = 50027

# GitHub constraints
MAX_DESCRIPTION_LENGTH = 350

# Git operation timeout in seconds
GIT_OPERATION_TIMEOUT = 60


class RepositoryService(Protocol):
    """Protocol for repository services (enables dependency injection)."""
    
    def is_configured(self) -> bool:
        """Check if the repository service is properly configured."""
        ...
    
    def create_repository(
        self,
        repo_name: str,
        description: str = "",
        private: bool = False
    ) -> Tuple[bool, str, Optional[str]]:
        """Create a new repository."""
        ...
    
    def create_and_push_project(
        self,
        project_path: Path,
        repo_name: str,
        description: str = "",
        private: bool = False
    ) -> Tuple[bool, str, Optional[str]]:
        """Create a repository and push project files."""
        ...


class GitHubManager:
    """Manages GitHub repository operations."""
    
    def __init__(
        self,
        token: Optional[str] = None,
        username: Optional[str] = None,
        enabled: Optional[bool] = None,
        base_dir: Optional[Path] = None
    ):
        """Initialize the GitHub manager with credentials.
        
        Args:
            token: GitHub personal access token. Defaults to config value.
            username: GitHub username. Defaults to config value.
            enabled: Whether GitHub integration is enabled. Defaults to config value.
            base_dir: Base directory for .gitignore. Defaults to config value.
        """
        self.enabled = enabled if enabled is not None else GITHUB_ENABLED
        self.token = token or GITHUB_TOKEN
        self.username = username or GITHUB_USERNAME
        self._base_dir = base_dir or BASE_DIR
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
    
    def sanitize_description(self, description: str) -> str:
        """Sanitize a repository description for GitHub.
        
        Args:
            description: The raw description text.
            
        Returns:
            A sanitized description suitable for a GitHub repository.
        """
        import re
        
        # Remove any quotes and trim whitespace
        description = description.strip().strip('"\'').strip()
        
        # Remove control characters and non-printable characters
        description = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', description)
        
        # Replace multiple whitespace with single space
        description = re.sub(r'\s+', ' ', description)
        
        # Remove any emoji or special unicode characters that GitHub might reject
        # Keep only ASCII printable characters
        description = ''.join(
            char for char in description 
            if 32 <= ord(char) < 127
        )
        
        # Truncate to GitHub's max length
        if len(description) > MAX_DESCRIPTION_LENGTH:
            description = description[:MAX_DESCRIPTION_LENGTH - 3].rstrip() + '...'
        
        return description
    
    def copy_gitignore(self, project_path: Path) -> bool:
        """
        Copy the root .gitignore to the project directory.
        
        Args:
            project_path: Path to the project directory
            
        Returns:
            True if successful, False otherwise
        """
        source_gitignore = self._base_dir / ".gitignore"
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
            logger.warning("GitHub integration not configured - missing token or username")
            return False, "GitHub integration not configured", None
        
        logger.info(f"Attempting to create repository: name='{repo_name}', private={private}, description_length={len(description)}")
        
        try:
            logger.debug("Fetching authenticated GitHub user...")
            user = self.github.get_user()
            logger.info(f"Authenticated as GitHub user: {user.login}")
            
            logger.debug(f"Creating repository '{repo_name}' for user '{user.login}'...")
            repo = user.create_repo(
                name=repo_name,
                description=description,
                private=private,
                auto_init=False  # We'll push our own content
            )
            logger.info(f"Created GitHub repository: {repo.full_name}")
            return True, f"Repository created: {repo.html_url}", repo.clone_url
        except GithubException as e:
            # Extract detailed error information
            status_code = getattr(e, 'status', 'unknown')
            error_data = getattr(e, 'data', {})
            error_message = error_data.get('message', str(e)) if isinstance(error_data, dict) else str(e)
            errors_list = error_data.get('errors', []) if isinstance(error_data, dict) else []
            documentation_url = error_data.get('documentation_url', '') if isinstance(error_data, dict) else ''
            
            # Log comprehensive error details
            logger.error(f"GitHub API error creating repository '{repo_name}':")
            logger.error(f"  HTTP Status: {status_code}")
            logger.error(f"  Message: {error_message}")
            if errors_list:
                for idx, err in enumerate(errors_list):
                    logger.error(f"  Error[{idx}]: {err}")
            if documentation_url:
                logger.error(f"  Documentation: {documentation_url}")
            logger.error(f"  Full error data: {error_data}")
            
            # Build user-friendly error message with details
            user_msg = f"GitHub API error (HTTP {status_code}): {error_message}"
            if errors_list:
                error_details = "; ".join(str(err) for err in errors_list)
                user_msg += f" - Details: {error_details}"
            
            return False, user_msg, None
        except Exception as e:
            logger.error(f"Unexpected error creating repository '{repo_name}': {type(e).__name__}: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            error_msg = f"Failed to create repository: {type(e).__name__}: {e}"
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
            logger.warning("GitHub integration not configured for init_and_push")
            return False, "GitHub integration not configured"
        
        logger.info(f"Starting git init and push for repo '{repo_name}' at path '{project_path}'")
        
        try:
            # Get the authenticated user's info from GitHub API
            logger.debug("Fetching authenticated user info for git config...")
            user = self.github.get_user()
            git_name = user.name or user.login
            git_email = user.email or f"{user.login}@users.noreply.github.com"
            
            logger.info(f"Using git identity: {git_name} <{git_email}>")
            
            # Build the authenticated remote URL
            remote_url = f"https://{user.login}:{self.token}@github.com/{user.login}/{repo_name}.git"
            logger.debug(f"Remote URL configured for user: {user.login}")
            
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
                # Create safe command for logging (hide token in remote URL)
                if cmd[0] == "git" and len(cmd) > 1:
                    if "remote" in cmd:
                        safe_cmd_str = "git remote add origin https://***@github.com/..."
                    else:
                        safe_cmd_str = " ".join(cmd)
                else:
                    safe_cmd_str = " ".join(cmd)
                
                logger.debug(f"Executing: {safe_cmd_str}")
                
                result = subprocess.run(
                    cmd,
                    cwd=str(project_path),
                    capture_output=True,
                    text=True,
                    timeout=GIT_OPERATION_TIMEOUT
                )
                
                if result.returncode != 0:
                    # Don't log the full command as it may contain the token
                    logger.error(f"Git command failed: {safe_cmd_str}")
                    logger.error(f"  Exit code: {result.returncode}")
                    logger.error(f"  Stderr: {result.stderr}")
                    logger.error(f"  Stdout: {result.stdout}")
                    error_msg = f"Git command failed ({safe_cmd_str}): {result.stderr.strip()}"
                    return False, error_msg
                else:
                    logger.debug(f"Git command succeeded: {safe_cmd_str}")
            
            public_url = f"https://github.com/{user.login}/{repo_name}"
            logger.info(f"Successfully pushed to GitHub: {public_url}")
            return True, f"Pushed to GitHub: {public_url}"
            
        except subprocess.TimeoutExpired as e:
            logger.error(f"Git operation timed out after {GIT_OPERATION_TIMEOUT} seconds: {e}")
            error_msg = f"Git operation timed out after {GIT_OPERATION_TIMEOUT} seconds"
            return False, error_msg
        except Exception as e:
            import traceback
            logger.error(f"Failed to push to GitHub: {type(e).__name__}: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            error_msg = f"Failed to push to GitHub: {type(e).__name__}: {e}"
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
        logger.info(f"Starting create_and_push_project workflow for '{repo_name}'")
        logger.debug(f"  project_path: {project_path}")
        logger.debug(f"  private: {private}")
        logger.debug(f"  description length: {len(description)}")
        
        if not self.is_configured():
            logger.warning("GitHub integration not configured - missing GITHUB_TOKEN or GITHUB_USERNAME")
            return False, "GitHub integration not configured. Set GITHUB_TOKEN and GITHUB_USERNAME in .env", None
        
        # Get the authenticated user's login
        try:
            logger.debug("Fetching authenticated GitHub user...")
            user = self.github.get_user()
            user_login = user.login
            logger.info(f"Authenticated as GitHub user: {user_login}")
        except Exception as e:
            import traceback
            logger.error(f"Failed to get GitHub user info: {type(e).__name__}: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return False, f"Failed to get GitHub user info: {e}", None
        
        # Step 1: Copy .gitignore
        logger.debug("Step 1: Copying .gitignore...")
        self.copy_gitignore(project_path)
        
        # Step 2: Create the repository
        logger.info("Step 2: Creating GitHub repository...")
        success, message, clone_url = self.create_repository(
            repo_name=repo_name,
            description=description,
            private=private
        )
        if not success:
            logger.error(f"Repository creation failed: {message}")
            return False, message, None
        logger.info(f"Repository created successfully: {clone_url}")
        
        # Step 3: Initialize and push
        logger.info("Step 3: Initializing git and pushing...")
        success, push_message = self.init_and_push(project_path, repo_name)
        if not success:
            logger.error(f"Git init/push failed: {push_message}")
            return False, push_message, None
        
        github_url = f"https://github.com/{user_login}/{repo_name}"
        logger.info(f"create_and_push_project completed successfully: {github_url}")
        return True, f"Project pushed to GitHub: {github_url}", github_url


# Singleton instance for easy access
github_manager = GitHubManager()
