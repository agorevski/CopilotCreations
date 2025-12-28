"""
Utility modules for the Discord Copilot Bot.
"""

from .logging import setup_logging, get_logger, SessionLogCollector
from .folder_utils import (
    load_folderignore,
    is_ignored,
    count_files_recursive,
    count_files_excluding_ignored,
    get_folder_tree,
    sanitize_username
)
from .text_utils import truncate_output, format_error_message
from .github import GitHubManager, github_manager
from .async_buffer import AsyncOutputBuffer
from .naming import RepositoryNamingGenerator, naming_generator

__all__ = [
    "setup_logging",
    "get_logger",
    "SessionLogCollector",
    "load_folderignore",
    "is_ignored",
    "count_files_recursive",
    "count_files_excluding_ignored",
    "get_folder_tree",
    "sanitize_username",
    "truncate_output",
    "format_error_message",
    "GitHubManager",
    "github_manager",
    "AsyncOutputBuffer",
    "RepositoryNamingGenerator",
    "naming_generator"
]
