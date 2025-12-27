"""
Utility modules for the Discord Copilot Bot.
"""

from .logging import setup_logging, SessionLogCollector
from .folder_utils import (
    load_folderignore,
    is_ignored,
    count_files_recursive,
    count_files_excluding_ignored,
    get_folder_tree,
    sanitize_username
)
from .text_utils import truncate_output

__all__ = [
    "setup_logging",
    "SessionLogCollector",
    "load_folderignore",
    "is_ignored",
    "count_files_recursive",
    "count_files_excluding_ignored",
    "get_folder_tree",
    "sanitize_username",
    "truncate_output"
]
