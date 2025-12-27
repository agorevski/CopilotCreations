"""
Tests for folder utility functions.
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
    load_folderignore
)


class TestSanitizeUsername:
    """Tests for sanitize_username function."""
    
    def test_normal_username(self):
        assert sanitize_username("john_doe") == "john_doe"
    
    def test_username_with_special_chars(self):
        result = sanitize_username("user<>:name")
        assert "<" not in result
        assert ">" not in result
        assert ":" not in result
    
    def test_empty_username(self):
        assert sanitize_username("") == "unknown_user"
    
    def test_username_with_dots_only(self):
        assert sanitize_username("...") == "unknown_user"
    
    def test_long_username_truncated(self):
        long_name = "a" * 100
        result = sanitize_username(long_name)
        assert len(result) <= 50
    
    def test_username_with_backslash(self):
        result = sanitize_username("user\\name")
        assert "\\" not in result
    
    def test_username_with_forward_slash(self):
        result = sanitize_username("user/name")
        assert "/" not in result
    
    def test_username_with_pipe(self):
        result = sanitize_username("user|name")
        assert "|" not in result
    
    def test_username_with_question_mark(self):
        result = sanitize_username("user?name")
        assert "?" not in result
    
    def test_username_with_asterisk(self):
        result = sanitize_username("user*name")
        assert "*" not in result
    
    def test_username_with_quotes(self):
        result = sanitize_username('user"name')
        assert '"' not in result
    
    def test_username_with_leading_trailing_dots(self):
        result = sanitize_username(".user.")
        assert not result.startswith(".")
        assert not result.endswith(".")
    
    def test_username_with_spaces(self):
        result = sanitize_username("  user  ")
        assert not result.startswith(" ")
        assert not result.endswith(" ")


class TestLoadFolderignore:
    """Tests for load_folderignore function."""
    
    def test_loads_from_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            ignore_file = tmppath / ".folderignore"
            ignore_file.write_text("node_modules/\ndist/\n# comment\n\n")
            
            patterns = load_folderignore(tmppath)
            
            assert "node_modules" in patterns
            assert "dist" in patterns
            assert "# comment" not in patterns
    
    def test_returns_empty_for_missing_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            patterns = load_folderignore(Path(tmpdir))
            # May return empty or patterns from parent/script dir
            assert isinstance(patterns, set)
    
    def test_strips_trailing_slashes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            ignore_file = tmppath / ".folderignore"
            ignore_file.write_text("folder_with_slash/\n")
            
            patterns = load_folderignore(tmppath)
            
            assert "folder_with_slash" in patterns
    
    def test_skips_empty_lines(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            ignore_file = tmppath / ".folderignore"
            ignore_file.write_text("pattern1\n\n\npattern2\n")
            
            patterns = load_folderignore(tmppath)
            
            assert "" not in patterns
            assert "pattern1" in patterns
            assert "pattern2" in patterns


class TestIsIgnored:
    """Tests for is_ignored function."""
    
    def test_exact_match(self):
        patterns = {"node_modules", "dist"}
        assert is_ignored("node_modules", patterns) is True
        assert is_ignored("dist", patterns) is True
    
    def test_no_match(self):
        patterns = {"node_modules", "dist"}
        assert is_ignored("src", patterns) is False
    
    def test_glob_pattern(self):
        patterns = {"*.pyc", "__pycache__"}
        assert is_ignored("file.pyc", patterns) is True
        assert is_ignored("__pycache__", patterns) is True
    
    def test_empty_patterns(self):
        assert is_ignored("anything", set()) is False
    
    def test_pattern_with_trailing_slash(self):
        patterns = {"build/"}
        assert is_ignored("build", patterns) is True
    
    def test_wildcard_prefix(self):
        patterns = {"*.log"}
        assert is_ignored("error.log", patterns) is True
        assert is_ignored("debug.log", patterns) is True
        assert is_ignored("file.txt", patterns) is False


class TestCountFilesRecursive:
    """Tests for count_files_recursive function."""
    
    def test_empty_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            assert count_files_recursive(Path(tmpdir)) == 0
    
    def test_directory_with_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            (tmppath / "file1.txt").touch()
            (tmppath / "file2.txt").touch()
            assert count_files_recursive(tmppath) == 2
    
    def test_nested_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            (tmppath / "file1.txt").touch()
            subdir = tmppath / "subdir"
            subdir.mkdir()
            (subdir / "file2.txt").touch()
            assert count_files_recursive(tmppath) == 2
    
    def test_deeply_nested(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            deep = tmppath / "a" / "b" / "c"
            deep.mkdir(parents=True)
            (deep / "file.txt").touch()
            assert count_files_recursive(tmppath) == 1


class TestCountFilesExcludingIgnored:
    """Tests for count_files_excluding_ignored function."""
    
    def test_excludes_ignored_dirs(self):
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
            
            patterns = {"node_modules"}
            file_count, dir_count = count_files_excluding_ignored(tmppath, patterns)
            
            assert file_count == 2  # file1.txt and main.py
            assert dir_count == 1   # src only
    
    def test_counts_all_without_ignore(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            (tmppath / "file.txt").touch()
            subdir = tmppath / "subdir"
            subdir.mkdir()
            (subdir / "file2.txt").touch()
            
            file_count, dir_count = count_files_excluding_ignored(tmppath, set())
            
            assert file_count == 2
            assert dir_count == 1
    
    def test_multiple_ignored_dirs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            
            for name in ["node_modules", "dist", "build"]:
                d = tmppath / name
                d.mkdir()
                (d / "file.txt").touch()
            
            patterns = {"node_modules", "dist", "build"}
            file_count, dir_count = count_files_excluding_ignored(tmppath, patterns)
            
            assert file_count == 0
            assert dir_count == 0


class TestGetFolderTree:
    """Tests for get_folder_tree function."""
    
    def test_empty_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = get_folder_tree(Path(tmpdir))
            assert result == "(empty folder)"
    
    def test_directory_with_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            (tmppath / "file1.txt").touch()
            result = get_folder_tree(tmppath)
            assert "file1.txt" in result
    
    def test_nonexistent_directory(self):
        result = get_folder_tree(Path("/nonexistent/path"))
        assert "not yet created" in result
    
    def test_ignored_folder_collapsed(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            
            # Create ignored directory with files
            node_modules = tmppath / "node_modules"
            node_modules.mkdir()
            (node_modules / "package.json").touch()
            (node_modules / "index.js").touch()
            
            patterns = {"node_modules"}
            result = get_folder_tree(tmppath, ignore_patterns=patterns)
            
            assert "node_modules/" in result
            assert "(2 files)" in result
            assert "package.json" not in result  # Should not show contents
    
    def test_max_depth_limit(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            
            # Create deeply nested structure
            current = tmppath
            for i in range(10):
                current = current / f"level{i}"
                current.mkdir()
                (current / "file.txt").touch()
            
            result = get_folder_tree(tmppath, max_depth=2)
            
            # Should truncate with ...
            assert "..." in result
    
    def test_sorts_directories_first(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            (tmppath / "zfile.txt").touch()
            (tmppath / "adir").mkdir()
            
            result = get_folder_tree(tmppath)
            
            # Directory should appear before file
            adir_pos = result.find("adir")
            zfile_pos = result.find("zfile")
            assert adir_pos < zfile_pos
    
    def test_tree_connectors(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            (tmppath / "file1.txt").touch()
            (tmppath / "file2.txt").touch()
            
            result = get_folder_tree(tmppath)
            
            # Should contain tree connectors
            assert "├──" in result or "└──" in result

