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
    sanitize_username,
)
from .text_utils import truncate_output, format_error_message
from .github import GitHubManager, github_manager
from .async_buffer import AsyncOutputBuffer
from .naming import RepositoryNamingGenerator, naming_generator
from .process_registry import ProcessRegistry, get_process_registry
from .session_manager import (
    SessionManager,
    PromptSession,
    get_session_manager,
    reset_session_manager,
)
from .prompt_refinement import (
    PromptRefinementService,
    get_refinement_service,
    reset_refinement_service,
)
from .azure_openai_client import (
    AzureOpenAIClient,
    get_azure_openai_client,
    reset_azure_openai_client,
)

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
    "naming_generator",
    "ProcessRegistry",
    "get_process_registry",
    "SessionManager",
    "PromptSession",
    "get_session_manager",
    "reset_session_manager",
    "PromptRefinementService",
    "get_refinement_service",
    "reset_refinement_service",
    "AzureOpenAIClient",
    "get_azure_openai_client",
    "reset_azure_openai_client",
]
