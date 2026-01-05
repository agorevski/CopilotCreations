"""
Folder and file utilities for the Discord Copilot Bot.
"""

import fnmatch
import logging
import re
from pathlib import Path
from typing import Set, Tuple

logger = logging.getLogger("copilot_bot")


# Constants for username sanitization
MAX_USERNAME_LENGTH = 50
DEFAULT_USERNAME = "unknown_user"


def sanitize_username(username: str) -> str:
    """Sanitize username to be safe for folder paths.

    Removes or replaces characters that are invalid in file system paths,
    strips leading/trailing dots and spaces, and truncates to maximum length.

    Args:
        username: The original username to sanitize.

    Returns:
        A sanitized username safe for use in folder paths. Returns DEFAULT_USERNAME
        if the sanitized result is empty.
    """
    sanitized = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', username)
    sanitized = sanitized.strip('. ')
    sanitized = sanitized[:MAX_USERNAME_LENGTH]
    return sanitized if sanitized else DEFAULT_USERNAME


def load_folderignore(base_path: Path) -> Set[str]:
    """Load patterns from .folderignore file.

    Searches for a .folderignore file starting from base_path and moving up
    through parent directories. Falls back to the script directory if not found.

    Args:
        base_path: The starting directory path to search for .folderignore.

    Returns:
        A set of ignore patterns. Empty set if no .folderignore file is found
        or if the file cannot be read.
    """
    patterns = set()
    folderignore_path = base_path / ".folderignore"
    
    # Also check parent directories for .folderignore
    current = base_path
    while current != current.parent:
        ignore_file = current / ".folderignore"
        if ignore_file.exists():
            folderignore_path = ignore_file
            break
        current = current.parent
    
    if not folderignore_path.exists():
        # Check in script directory as fallback
        script_dir = Path(__file__).parent.parent.parent
        folderignore_path = script_dir / ".folderignore"
    
    if folderignore_path.exists():
        try:
            with open(folderignore_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    # Skip comments and empty lines
                    if line and not line.startswith('#'):
                        # Remove trailing slash for matching
                        patterns.add(line.rstrip('/'))
        except PermissionError:
            logger.warning(f"Permission denied reading {folderignore_path}")
        except UnicodeDecodeError as e:
            logger.warning(f"Encoding error in {folderignore_path}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error reading {folderignore_path}: {e}")
    
    return patterns


def is_ignored(item_name: str, patterns: Set[str]) -> bool:
    """Check if an item matches any ignore pattern.

    Uses fnmatch for pattern matching, supporting wildcards like * and ?.

    Args:
        item_name: The name of the file or directory to check.
        patterns: A set of glob-style patterns to match against.

    Returns:
        True if the item matches any pattern, False otherwise.
    """
    for pattern in patterns:
        # Match against the item name
        if fnmatch.fnmatch(item_name, pattern):
            return True
        if fnmatch.fnmatch(item_name, pattern.rstrip('/')):
            return True
    return False


def count_files_recursive(path: Path) -> int:
    """Count all files recursively in a directory.

    Args:
        path: The directory path to count files in.

    Returns:
        The total number of files in the directory and all subdirectories.
        Returns 0 if permission is denied.
    """
    try:
        return sum(1 for _ in path.rglob('*') if _.is_file())
    except PermissionError:
        return 0


def count_files_excluding_ignored(path: Path, ignore_patterns: Set[str] = None) -> Tuple[int, int]:
    """Count files and directories excluding ignored folders.

    Recursively counts files and directories while respecting ignore patterns.
    Ignored directories are skipped entirely, not traversed.

    Args:
        path: The directory path to count items in.
        ignore_patterns: Optional set of patterns to exclude. If None, patterns
            are loaded from .folderignore file.

    Returns:
        A tuple of (file_count, directory_count) excluding ignored items.
    """
    if ignore_patterns is None:
        ignore_patterns = load_folderignore(path)
    
    file_count = 0
    dir_count = 0
    
    def count_recursive(current_path: Path):
        nonlocal file_count, dir_count
        try:
            for item in current_path.iterdir():
                if item.is_dir():
                    if is_ignored(item.name, ignore_patterns):
                        # Skip ignored directories entirely
                        continue
                    dir_count += 1
                    count_recursive(item)
                elif item.is_file():
                    file_count += 1
        except PermissionError:
            pass
    
    count_recursive(path)
    return file_count, dir_count


def _get_inline_path(
    path: Path,
    max_depth: int,
    current_depth: int,
    ignore_patterns: Set[str]
) -> Tuple[str, bool]:
    """Check if a directory should be inlined (empty or single child).

    Determines whether a directory path can be collapsed into a single line
    representation (e.g., "parent/child/file.txt" instead of nested tree).

    Args:
        path: The directory path to check.
        max_depth: Maximum depth to traverse.
        current_depth: Current depth in the tree traversal.
        ignore_patterns: Set of patterns to exclude from consideration.

    Returns:
        A tuple of (inline_suffix, is_terminal) where:
            - inline_suffix: The path string to append (e.g., "/child/file.txt").
            - is_terminal: True if this is the end of an inlinable chain.
    """
    if current_depth > max_depth:
        return "", False
    
    try:
        all_items = sorted(path.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
        items = [item for item in all_items if not is_ignored(item.name, ignore_patterns)]
    except PermissionError:
        return "", True
    
    if len(items) == 0:
        # Empty folder - signal to skip it
        return "", True
    
    if len(items) == 1:
        item = items[0]
        if item.is_file():
            return "/" + item.name, True
        else:
            # It's a directory - recurse to check if it can also be inlined
            suffix, is_terminal = _get_inline_path(
                item, max_depth, current_depth + 1, ignore_patterns
            )
            # If the nested path is terminal but has no suffix, it's an empty chain
            if is_terminal and not suffix:
                return "", True
            return "/" + item.name + suffix, is_terminal
    
    return "", False


def get_folder_tree(
    path: Path,
    prefix: str = "",
    max_depth: int = 4,
    current_depth: int = 0,
    ignore_patterns: Set[str] = None,
    max_files_inline: int = 10
) -> str:
    """Generate a folder tree representation, respecting .folderignore patterns.

    Creates a visual tree structure of directories and files. Files in the same
    directory are grouped on a single line (comma-separated). Empty directories
    are skipped, and single-child directory chains are inlined.

    Args:
        path: The root directory path to generate tree from.
        prefix: String prefix for indentation (used internally for recursion).
        max_depth: Maximum depth to traverse (default: 4).
        current_depth: Current depth in traversal (used internally for recursion).
        ignore_patterns: Optional set of patterns to exclude. If None, patterns
            are loaded from .folderignore file.
        max_files_inline: Maximum number of files to show before summarizing
            with "(+N files)" (default: 10).

    Returns:
        A string representation of the folder tree. Returns "(folder not yet
        created)" if path doesn't exist, or "(empty folder)" if no items remain
        after filtering.
    """
    if current_depth > max_depth:
        return prefix + "...\n"
    
    if not path.exists():
        return "(folder not yet created)\n"
    
    # Load ignore patterns on first call
    if ignore_patterns is None:
        ignore_patterns = load_folderignore(path)
    
    lines = []
    try:
        # Filter out ignored items first
        all_items = sorted(path.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
        items = [item for item in all_items if not is_ignored(item.name, ignore_patterns)]
        
        # Separate directories and files
        dirs = [item for item in items if item.is_dir()]
        files = [item for item in items if item.is_file()]
        
        # Process directories
        # First, filter out empty directories and collect non-empty ones with their inline info
        non_empty_dirs = []
        for item in dirs:
            inline_suffix, is_terminal = _get_inline_path(
                item, max_depth, current_depth + 1, ignore_patterns
            )
            # Skip empty directories (is_terminal=True with empty suffix)
            if is_terminal and not inline_suffix:
                continue
            non_empty_dirs.append((item, inline_suffix, is_terminal))
        
        for i, (item, inline_suffix, is_terminal) in enumerate(non_empty_dirs):
            is_last_dir = i == len(non_empty_dirs) - 1
            is_last = is_last_dir and len(files) == 0
            connector = "└ " if is_last else "├ "
            
            if is_terminal:
                lines.append(f"{prefix}{connector}{item.name}{inline_suffix}")
            else:
                lines.append(f"{prefix}{connector}{item.name}")
                extension = "    " if is_last else "│   "
                subtree = get_folder_tree(
                    item, prefix + extension, max_depth, current_depth + 1, 
                    ignore_patterns, max_files_inline
                )
                if subtree:
                    lines.append(subtree.rstrip('\n'))
        
        # Process files - group them on one line
        if files:
            connector = "└ " if True else "├ "  # Files are always last
            file_names = [f.name for f in files]
            
            if len(file_names) <= max_files_inline:
                # Show all files on one line
                files_str = ", ".join(file_names)
            else:
                # Show first max_files_inline files and count of remaining
                shown_files = file_names[:max_files_inline]
                remaining = len(file_names) - max_files_inline
                files_str = ", ".join(shown_files) + f" (+{remaining} files)"
            
            lines.append(f"{prefix}{connector}{files_str}")
    except PermissionError:
        lines.append(f"{prefix}(permission denied)")
    
    return '\n'.join(lines) if lines else "(empty folder)"
