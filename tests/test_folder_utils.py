"""
Tests for folder utility functions.

This module tests folder-related utilities including username sanitization,
folder ignore patterns, file counting, and folder tree generation.
"""

import tempfile
from pathlib import Path

import pytest

from src.utils.folder_utils import (
    sanitize_username,
    is_ignored,
    count_files_recursive,
    count_files_excluding_ignored,
    get_folder_tree,
    load_folderignore,
    MAX_USERNAME_LENGTH,
    DEFAULT_USERNAME
)


class TestSanitizeUsername:
    """Tests for sanitize_username function which cleans usernames for filesystem use."""
    
    def test_sanitization(self):
        """Test username sanitization for various cases.

        Tests that usernames are properly sanitized for filesystem use.

        Verifies:
            Normal username remains unchanged.
            Special characters (<>:"/\\|?*) are removed.
            Empty username returns default.
            Dots-only username returns default.
            Long username is truncated.
            Leading/trailing dots and spaces are stripped.
        """
        # Normal username unchanged
        assert sanitize_username("john_doe") == "john_doe"
        
        # Special characters removed
        result = sanitize_username("user<>:name")
        assert "<" not in result and ">" not in result and ":" not in result
        
        assert "\\" not in sanitize_username("user\\name")
        assert "/" not in sanitize_username("user/name")
        assert "|" not in sanitize_username("user|name")
        assert "?" not in sanitize_username("user?name")
        assert "*" not in sanitize_username("user*name")
        assert '"' not in sanitize_username('user"name')
        
        # Empty and dots-only return default
        assert sanitize_username("") == "unknown_user"
        assert sanitize_username("...") == "unknown_user"
        
        # Long username truncated
        result = sanitize_username("a" * 100)
        assert len(result) <= 50
        
        # Leading/trailing dots and spaces stripped
        result = sanitize_username(".user.")
        assert not result.startswith(".") and not result.endswith(".")
        
        result = sanitize_username("  user  ")
        assert not result.startswith(" ") and not result.endswith(" ")


class TestUsernameConstants:
    """Tests for username-related constants and their integration."""
    
    def test_constants_and_integration(self):
        """Test username constants and their integration with sanitize_username.

        Verifies:
            MAX_USERNAME_LENGTH is 50.
            DEFAULT_USERNAME is "unknown_user".
            sanitize_username respects MAX_USERNAME_LENGTH.
            sanitize_username returns DEFAULT_USERNAME for empty input.
        """
        assert isinstance(MAX_USERNAME_LENGTH, int)
        assert MAX_USERNAME_LENGTH > 0
        assert MAX_USERNAME_LENGTH == 50
        
        assert isinstance(DEFAULT_USERNAME, str)
        assert len(DEFAULT_USERNAME) > 0
        assert DEFAULT_USERNAME == "unknown_user"
        
        # Integration: long names truncated to max length
        long_name = "a" * (MAX_USERNAME_LENGTH + 50)
        result = sanitize_username(long_name)
        assert len(result) <= MAX_USERNAME_LENGTH
        
        # Integration: empty returns default
        assert sanitize_username("") == DEFAULT_USERNAME


class TestLoadFolderignore:
    """Tests for load_folderignore function which loads ignore patterns."""
    
    def test_load_patterns(self):
        """Test loading .folderignore patterns from a directory.

        Verifies:
            Patterns are loaded from .folderignore file in directory.
            Comments (lines starting with #) and empty lines are ignored.
            Trailing slashes are stripped from patterns.
            Returns empty set when .folderignore file is missing.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            
            # Load patterns from file
            ignore_file = tmppath / ".folderignore"
            ignore_file.write_text("node_modules/\ndist/\n# comment\n\n")
            
            patterns = load_folderignore(tmppath)
            assert "node_modules" in patterns
            assert "dist" in patterns
            assert "# comment" not in patterns
            
        # Missing file returns set (may be empty or from parent)
        with tempfile.TemporaryDirectory() as tmpdir2:
            patterns = load_folderignore(Path(tmpdir2))
            assert isinstance(patterns, set)
        
        # Strips trailing slashes
        with tempfile.TemporaryDirectory() as tmpdir3:
            ignore_file = Path(tmpdir3) / ".folderignore"
            ignore_file.write_text("folder_with_slash/\n")
            patterns = load_folderignore(Path(tmpdir3))
            assert "folder_with_slash" in patterns
        
        # Skips empty lines
        with tempfile.TemporaryDirectory() as tmpdir4:
            ignore_file = Path(tmpdir4) / ".folderignore"
            ignore_file.write_text("pattern1\n\n\npattern2\n")
            patterns = load_folderignore(Path(tmpdir4))
            assert "" not in patterns
            assert "pattern1" in patterns
            assert "pattern2" in patterns


class TestIsIgnored:
    """Tests for is_ignored function which checks if a path matches ignore patterns."""
    
    def test_pattern_matching(self):
        """Test pattern matching against ignore patterns.

        Verifies:
            Exact matches return True.
            Non-matching paths return False.
            Glob patterns (e.g., *.pyc) work correctly.
            Empty patterns set always returns False.
            Patterns with trailing slashes match directories.
            Wildcard prefix patterns (e.g., *.log) match appropriately.
        """
        # Exact match
        patterns = {"node_modules", "dist"}
        assert is_ignored("node_modules", patterns) is True
        assert is_ignored("dist", patterns) is True
        assert is_ignored("src", patterns) is False  # No match
        
        # Glob patterns
        glob_patterns = {"*.pyc", "__pycache__"}
        assert is_ignored("file.pyc", glob_patterns) is True
        assert is_ignored("__pycache__", glob_patterns) is True
        
        # Empty patterns
        assert is_ignored("anything", set()) is False
        
        # Trailing slash
        assert is_ignored("build", {"build/"}) is True
        
        # Wildcard prefix
        log_patterns = {"*.log"}
        assert is_ignored("error.log", log_patterns) is True
        assert is_ignored("debug.log", log_patterns) is True
        assert is_ignored("file.txt", log_patterns) is False


class TestCountFilesRecursive:
    """Tests for count_files_recursive function."""
    
    def test_file_counting(self):
        """Test recursive file counting in directories.

        Verifies:
            Empty directory returns 0.
            Directory with files returns correct count.
            Nested files are counted recursively.
            Deeply nested files are included in the count.
        """
        # Empty directory
        with tempfile.TemporaryDirectory() as tmpdir:
            assert count_files_recursive(Path(tmpdir)) == 0
        
        # With files
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            (tmppath / "file1.txt").touch()
            (tmppath / "file2.txt").touch()
            assert count_files_recursive(tmppath) == 2
        
        # Nested files
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            (tmppath / "file1.txt").touch()
            subdir = tmppath / "subdir"
            subdir.mkdir()
            (subdir / "file2.txt").touch()
            assert count_files_recursive(tmppath) == 2
        
        # Deeply nested
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            deep = tmppath / "a" / "b" / "c"
            deep.mkdir(parents=True)
            (deep / "file.txt").touch()
            assert count_files_recursive(tmppath) == 1


class TestCountFilesExcludingIgnored:
    """Tests for count_files_excluding_ignored function."""
    
    def test_exclusion_counting(self):
        """Test file counting with directory exclusions.

        Verifies:
            Ignored directories are excluded from counts.
            All files are counted when no ignore patterns provided.
            Multiple ignored directories are all excluded.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            
            # Create regular files
            (tmppath / "file1.txt").touch()
            src = tmppath / "src"
            src.mkdir()
            (src / "main.py").touch()
            
            # Create ignored directory
            node_modules = tmppath / "node_modules"
            node_modules.mkdir()
            (node_modules / "package.json").touch()
            
            # Excludes ignored
            file_count, dir_count = count_files_excluding_ignored(tmppath, {"node_modules"})
            assert file_count == 2  # file1.txt and main.py
            assert dir_count == 1   # src only
        
        # Counts all without patterns
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            (tmppath / "file.txt").touch()
            subdir = tmppath / "subdir"
            subdir.mkdir()
            (subdir / "file2.txt").touch()
            
            file_count, dir_count = count_files_excluding_ignored(tmppath, set())
            assert file_count == 2
            assert dir_count == 1
        
        # Multiple ignored
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            for name in ["node_modules", "dist", "build"]:
                d = tmppath / name
                d.mkdir()
                (d / "file.txt").touch()
            
            file_count, dir_count = count_files_excluding_ignored(tmppath, {"node_modules", "dist", "build"})
            assert file_count == 0
            assert dir_count == 0


class TestGetFolderTree:
    """Tests for get_folder_tree function which generates tree visualization."""
    
    def test_tree_generation(self):
        """Test folder tree generation and visualization.

        Verifies:
            Empty directory shows "(empty folder)".
            Generated tree contains file names.
            Non-existent path shows "not yet created".
            Ignored folders are hidden from output.
            Max depth parameter limits tree depth.
            Directories are sorted before files.
            Tree connectors (├, └) are present in output.
        """
        # Empty directory
        with tempfile.TemporaryDirectory() as tmpdir:
            result = get_folder_tree(Path(tmpdir))
            assert result == "(empty folder)"
        
        # With files
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            (tmppath / "file1.txt").touch()
            result = get_folder_tree(tmppath)
            assert "file1.txt" in result
        
        # Non-existent
        result = get_folder_tree(Path("/nonexistent/path"))
        assert "not yet created" in result
        
        # Ignored folders hidden
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            node_modules = tmppath / "node_modules"
            node_modules.mkdir()
            (node_modules / "package.json").touch()
            (tmppath / "readme.txt").touch()
            
            result = get_folder_tree(tmppath, ignore_patterns={"node_modules"})
            assert "node_modules" not in result
            assert "readme.txt" in result
        
        # Max depth limits
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            current = tmppath
            for i in range(10):
                current = current / f"level{i}"
                current.mkdir()
                (current / "file.txt").touch()
            
            result = get_folder_tree(tmppath, max_depth=2)
            assert "..." in result
        
        # Directories before files
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            (tmppath / "zfile.txt").touch()
            (tmppath / "adir").mkdir()
            (tmppath / "adir" / "placeholder.txt").touch()  # Need file for dir to show
            
            result = get_folder_tree(tmppath)
            adir_pos = result.find("adir")
            zfile_pos = result.find("zfile")
            assert adir_pos < zfile_pos
        
        # Tree connectors
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            (tmppath / "file1.txt").touch()
            (tmppath / "file2.txt").touch()
            result = get_folder_tree(tmppath)
            assert "├ " in result or "└ " in result
    
    def test_tree_formatting(self):
        """Test folder tree formatting and display options.

        Verifies:
            Empty folders are omitted from output.
            Single file is inlined with parent directory.
            Nested single-child paths are inlined (e.g., .github/workflows/ci.yaml).
            Multiple files are comma-separated.
            Files are truncated after max with (+N files) indicator.
            Directories appear before grouped files.
        """
        # Empty folders omitted
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            (tmppath / "workflows").mkdir()
            result = get_folder_tree(tmppath)
            assert "workflows" not in result
        
        # Single file inlined
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            workflows = tmppath / "workflows"
            workflows.mkdir()
            (workflows / "ci.yaml").touch()
            result = get_folder_tree(tmppath)
            assert "workflows/ci.yaml" in result
        
        # Nested single-child inlined
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            github = tmppath / ".github"
            github.mkdir()
            workflows = github / "workflows"
            workflows.mkdir()
            (workflows / "ci.yaml").touch()
            result = get_folder_tree(tmppath)
            assert ".github/workflows/ci.yaml" in result
        
        # Multiple files comma-separated
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            src = tmppath / "src"
            src.mkdir()
            for name in ["__init__.py", "cli.py", "models.py"]:
                (src / name).touch()
            result = get_folder_tree(tmppath)
            assert "__init__.py, cli.py, models.py" in result
        
        # Files truncated after max
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            src = tmppath / "src"
            src.mkdir()
            for i in range(15):
                (src / f"file{i:02d}.py").touch()
            result = get_folder_tree(tmppath, max_files_inline=10)
            assert "(+5 files)" in result
            assert "file00.py" in result
        
        # Exact max shows all
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            src = tmppath / "src"
            src.mkdir()
            for i in range(10):
                (src / f"file{i:02d}.py").touch()
            result = get_folder_tree(tmppath, max_files_inline=10)
            assert "(+" not in result
        
        # Dirs before grouped files
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            (tmppath / "src").mkdir()
            (tmppath / "src" / "main.py").touch()
            (tmppath / "tests").mkdir()
            (tmppath / "tests" / "test.py").touch()
            (tmppath / "README.md").touch()
            (tmppath / "setup.py").touch()
            
            result = get_folder_tree(tmppath)
            src_pos = result.find("src")
            readme_pos = result.find("README.md")
            assert src_pos < readme_pos
            assert "README.md, setup.py" in result

