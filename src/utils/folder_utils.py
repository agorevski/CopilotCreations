"""
Folder and file utilities for the Discord Copilot Bot.
"""

import fnmatch
import re
from pathlib import Path
from typing import Set, Tuple


def sanitize_username(username: str) -> str:
    """Sanitize username to be safe for folder paths."""
    sanitized = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', username)
    sanitized = sanitized.strip('. ')
    sanitized = sanitized[:50]  # Limit length
    return sanitized if sanitized else "unknown_user"


def load_folderignore(base_path: Path) -> Set[str]:
    """Load patterns from .folderignore file."""
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
        except Exception:
            pass
    
    return patterns


def is_ignored(item_name: str, patterns: Set[str]) -> bool:
    """Check if an item matches any ignore pattern."""
    for pattern in patterns:
        # Match against the item name
        if fnmatch.fnmatch(item_name, pattern):
            return True
        if fnmatch.fnmatch(item_name, pattern.rstrip('/')):
            return True
    return False


def count_files_recursive(path: Path) -> int:
    """Count all files recursively in a directory."""
    try:
        return sum(1 for _ in path.rglob('*') if _.is_file())
    except PermissionError:
        return 0


def count_files_excluding_ignored(path: Path, ignore_patterns: Set[str] = None) -> Tuple[int, int]:
    """Count files and directories excluding ignored folders."""
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


def get_folder_tree(
    path: Path,
    prefix: str = "",
    max_depth: int = 4,
    current_depth: int = 0,
    ignore_patterns: Set[str] = None
) -> str:
    """Generate a folder tree representation, respecting .folderignore patterns."""
    if current_depth > max_depth:
        return prefix + "...\n"
    
    if not path.exists():
        return "(folder not yet created)\n"
    
    # Load ignore patterns on first call
    if ignore_patterns is None:
        ignore_patterns = load_folderignore(path)
    
    lines = []
    try:
        items = sorted(path.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
        for i, item in enumerate(items):
            is_last = i == len(items) - 1
            connector = "└── " if is_last else "├── "
            
            if item.is_dir() and is_ignored(item.name, ignore_patterns):
                # Show collapsed view with file count
                file_count = count_files_recursive(item)
                lines.append(f"{prefix}{connector}{item.name}/ ({file_count} files)")
            else:
                lines.append(f"{prefix}{connector}{item.name}")
                
                if item.is_dir():
                    extension = "    " if is_last else "│   "
                    subtree = get_folder_tree(item, prefix + extension, max_depth, current_depth + 1, ignore_patterns)
                    if subtree:
                        lines.append(subtree.rstrip('\n'))
    except PermissionError:
        lines.append(f"{prefix}(permission denied)")
    
    return '\n'.join(lines) if lines else "(empty folder)"
