"""
Tests for text utility functions.

This module tests text manipulation utilities including truncation,
error formatting, and message splitting for Discord's character limits.
"""

import pytest

from src.utils.text_utils import truncate_output, format_error_message, split_message


class TestTruncateOutput:
    """Tests for truncate_output function which truncates long text from the beginning."""
    
    def test_truncation_behavior(self):
        """
        Tests truncation with various input lengths:
        - Short text (unchanged)
        - Exact length text (unchanged)  
        - Long text (truncated with ... prefix)
        - Empty string handling
        - Default max_length from config
        """
        # Short text unchanged
        short_text = "Hello, world!"
        assert truncate_output(short_text, max_length=100) == short_text
        
        # Exact length unchanged
        exact_text = "a" * 100
        assert truncate_output(exact_text, max_length=100) == exact_text
        
        # Long text truncated with ... prefix, preserving end
        long_text = "start_" + "x" * 100 + "_end"
        result = truncate_output(long_text, max_length=50)
        assert len(result) == 50
        assert result.startswith("...")
        assert result.endswith("_end")  # Preserves end of output
        assert "start_" not in result
        
        # Empty string handling
        assert truncate_output("", max_length=100) == ""
        
        # Test default max_length from config
        from src.config import MAX_MESSAGE_LENGTH
        text = "a" * 100
        assert truncate_output(text) == text  # Unchanged since < MAX_MESSAGE_LENGTH


class TestFormatErrorMessage:
    """Tests for format_error_message function which formats errors for Discord display."""
    
    def test_error_formatting(self):
        """
        Tests error message formatting options:
        - With traceback (code block formatting)
        - Without traceback (inline formatting)
        - Default include_traceback=True
        """
        # With traceback - uses code block
        result_with_tb = format_error_message("Test Error", "Error details", include_traceback=True)
        assert "❌" in result_with_tb
        assert "**Test Error**" in result_with_tb
        assert "```" in result_with_tb
        assert "Error details" in result_with_tb
        
        # Without traceback - no code block
        result_no_tb = format_error_message("Test Error", "Error details", include_traceback=False)
        assert "❌" in result_no_tb
        assert "**Test Error:**" in result_no_tb
        assert "```" not in result_no_tb
        assert "Error details" in result_no_tb
        
        # Default includes traceback
        result_default = format_error_message("Test Error", "Details")
        assert "```" in result_default


class TestSplitMessage:
    """Tests for split_message function which splits long messages at natural break points."""
    
    def test_split_behavior(self):
        """
        Tests message splitting at various break points:
        - Short messages (unchanged, single-item list)
        - Splits at paragraph breaks (\\n\\n)
        - Splits at newlines (\\n)
        - Splits at sentences (.)
        - Splits at spaces
        - Hard breaks for text without spaces
        - All chunks stay within limit
        """
        # Short message unchanged
        short = "Hello, world!"
        assert split_message(short, max_length=100) == [short]
        
        # Exact length unchanged
        exact = "a" * 100
        assert split_message(exact, max_length=100) == [exact]
        
        # Splits at paragraph breaks
        para_text = "First paragraph.\n\nSecond paragraph."
        para_result = split_message(para_text, max_length=25)
        assert len(para_result) == 2
        assert para_result[0] == "First paragraph."
        assert para_result[1] == "Second paragraph."
        
        # Splits at newlines
        line_text = "First line.\nSecond line.\nThird line."
        line_result = split_message(line_text, max_length=20)
        assert len(line_result) >= 2
        assert "First line." in line_result[0]
        
        # Splits at sentences
        sent_text = "First sentence. Second sentence. Third sentence."
        sent_result = split_message(sent_text, max_length=25)
        assert len(sent_result) >= 2
        assert sent_result[0].endswith(".")
        
        # Splits at spaces
        space_text = "word " * 50  # 250 characters
        space_result = split_message(space_text, max_length=100)
        assert len(space_result) >= 3
        for chunk in space_result:
            assert len(chunk) <= 100
        
        # Hard break when no spaces
        no_space = "a" * 250
        no_space_result = split_message(no_space, max_length=100)
        assert len(no_space_result) == 3
        assert no_space_result[0] == "a" * 100
        assert no_space_result[1] == "a" * 100
        assert no_space_result[2] == "a" * 50
        
        # Empty string
        assert split_message("", max_length=100) == [""]
        
        # All chunks within limit for long text
        long_text = "This is a test. " * 200
        chunks = split_message(long_text, max_length=100)
        for chunk in chunks:
            assert len(chunk) <= 100
