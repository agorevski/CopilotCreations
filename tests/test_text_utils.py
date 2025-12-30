"""
Tests for text utility functions.
"""

import pytest

from src.utils.text_utils import truncate_output, format_error_message, split_message


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


class TestSplitMessage:
    """Tests for split_message function."""
    
    def test_short_message_unchanged(self):
        """Short messages should return as single-item list."""
        text = "Hello, world!"
        result = split_message(text, max_length=100)
        assert result == [text]
    
    def test_exact_length_unchanged(self):
        """Message exactly at max_length should not be split."""
        text = "a" * 100
        result = split_message(text, max_length=100)
        assert result == [text]
    
    def test_splits_at_paragraph(self):
        """Should prefer splitting at paragraph breaks."""
        text = "First paragraph.\n\nSecond paragraph."
        result = split_message(text, max_length=25)
        assert len(result) == 2
        assert result[0] == "First paragraph."
        assert result[1] == "Second paragraph."
    
    def test_splits_at_newline(self):
        """Should split at newline if no paragraph break available."""
        text = "First line.\nSecond line.\nThird line."
        result = split_message(text, max_length=20)
        assert len(result) >= 2
        assert "First line." in result[0]
    
    def test_splits_at_sentence(self):
        """Should split at sentence boundaries."""
        text = "First sentence. Second sentence. Third sentence."
        result = split_message(text, max_length=25)
        assert len(result) >= 2
        # Each chunk should end at a sentence boundary
        assert result[0].endswith(".")
    
    def test_splits_at_space(self):
        """Should split at space if no better break point."""
        text = "word " * 50  # 250 characters
        result = split_message(text, max_length=100)
        assert len(result) >= 3
        for chunk in result:
            assert len(chunk) <= 100
    
    def test_hard_break_no_spaces(self):
        """Should hard break if no spaces available."""
        text = "a" * 250
        result = split_message(text, max_length=100)
        assert len(result) == 3
        assert result[0] == "a" * 100
        assert result[1] == "a" * 100
        assert result[2] == "a" * 50
    
    def test_empty_string(self):
        """Empty string should return list with empty string."""
        result = split_message("", max_length=100)
        assert result == [""]
    
    def test_all_chunks_within_limit(self):
        """All chunks should be within the max_length limit."""
        text = "This is a test. " * 200  # Long text
        result = split_message(text, max_length=100)
        for chunk in result:
            assert len(chunk) <= 100
