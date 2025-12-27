"""
Tests for text utility functions.
"""

import pytest

from src.utils.text_utils import truncate_output


class TestTruncateOutput:
    """Tests for truncate_output function."""
    
    def test_short_output_unchanged(self):
        text = "Hello, world!"
        result = truncate_output(text, max_length=100)
        assert result == text
    
    def test_exact_length_unchanged(self):
        text = "a" * 100
        result = truncate_output(text, max_length=100)
        assert result == text
    
    def test_long_output_truncated(self):
        text = "a" * 200
        result = truncate_output(text, max_length=100)
        assert len(result) == 100
        assert result.startswith("...")
    
    def test_preserves_end_of_output(self):
        text = "start_" + "x" * 100 + "_end"
        result = truncate_output(text, max_length=50)
        assert result.endswith("_end")
        assert "start_" not in result
    
    def test_empty_string(self):
        assert truncate_output("", max_length=100) == ""
