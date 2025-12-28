"""
Tests for text utility functions.
"""

import pytest

from src.utils.text_utils import truncate_output, format_error_message


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
    
    def test_uses_default_max_length(self):
        """Test that default max_length is used when not specified."""
        from src.config import MAX_MESSAGE_LENGTH
        text = "a" * 100
        result = truncate_output(text)
        assert result == text  # Should be unchanged since 100 < MAX_MESSAGE_LENGTH


class TestFormatErrorMessage:
    """Tests for format_error_message function."""
    
    def test_with_traceback(self):
        """Test error message formatting with traceback."""
        result = format_error_message("Test Error", "Some error details", include_traceback=True)
        assert "❌" in result
        assert "**Test Error**" in result
        assert "```" in result
        assert "Some error details" in result
    
    def test_without_traceback(self):
        """Test error message formatting without traceback."""
        result = format_error_message("Test Error", "Some error details", include_traceback=False)
        assert "❌" in result
        assert "**Test Error:**" in result
        assert "```" not in result
        assert "Some error details" in result
    
    def test_default_include_traceback(self):
        """Test that include_traceback defaults to True."""
        result = format_error_message("Test Error", "Details")
        assert "```" in result  # Code block indicates traceback formatting
