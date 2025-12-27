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
