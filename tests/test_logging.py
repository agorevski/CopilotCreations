"""
Tests for logging utilities.

This module tests the SessionLogCollector class which collects and formats
logs during project creation sessions for debugging and audit purposes.
"""

import pytest

from src.utils.logging import SessionLogCollector


class TestSessionLogCollector:
    """Tests for SessionLogCollector class covering initialization, logging, and markdown export."""
    
    def test_initialization_and_logging_levels(self):
        """Test collector initialization and all logging levels.

        Verifies that initialization sets session ID and empty logs list,
        INFO, WARNING, and ERROR log levels work correctly, and multiple
        log entries accumulate in order.

        Returns:
            None

        Raises:
            AssertionError: If any logging level or initialization check fails.
        """
        # Test initialization
        collector = SessionLogCollector("test_session")
        assert collector.session_id == "test_session"
        assert collector.logs == []
        
        # Test all log levels
        collector.info("Info message")
        assert len(collector.logs) == 1
        assert "INFO" in collector.logs[0]
        assert "Info message" in collector.logs[0]
        
        collector.warning("Warning message")
        assert len(collector.logs) == 2
        assert "WARNING" in collector.logs[1]
        
        collector.error("Error message")
        assert len(collector.logs) == 3
        assert "ERROR" in collector.logs[2]
    
    def test_get_markdown_basic(self):
        """Test markdown export includes all required sections.

        Verifies that the generated markdown contains the header with session ID,
        prompt and model info, status and file/dir counts, log entries and
        Copilot Output section.

        Returns:
            None

        Raises:
            AssertionError: If any required markdown section is missing.
        """
        collector = SessionLogCollector("test_session")
        collector.info("Test log entry")
        
        md = collector.get_markdown(
            prompt="Test prompt",
            model="gpt-4",
            status="COMPLETED",
            file_count=5,
            dir_count=2
        )
        
        assert "# Project Creation Log" in md
        assert "test_session" in md
        assert "Test prompt" in md
        assert "gpt-4" in md
        assert "COMPLETED" in md
        assert "Files Created:** 5" in md
        assert "Directories Created:** 2" in md
        assert "Test log entry" in md
        assert "## Copilot Output" in md
    
    def test_get_markdown_with_copilot_output(self):
        """Test markdown export with Copilot output.

        Verifies that the Copilot output section is populated correctly,
        multiline output is preserved, special characters and unicode are
        handled correctly, and empty output still shows section header.

        Returns:
            None

        Raises:
            AssertionError: If Copilot output is not correctly rendered in markdown.
        """
        collector = SessionLogCollector("test_session")
        
        copilot_output = """Creating project structure...
Generating main.py...
Done! Created 3 files."""
        
        md = collector.get_markdown(
            prompt="Create a Python hello world project",
            model="gpt-4",
            status="COMPLETED SUCCESSFULLY",
            file_count=3,
            dir_count=1,
            copilot_output=copilot_output
        )
        
        assert "## Copilot Output" in md
        assert "Creating project structure..." in md
        assert "Done! Created 3 files." in md
        
        # Test empty output still shows section
        collector2 = SessionLogCollector("test2")
        md2 = collector2.get_markdown(
            prompt="Test", model="default", status="ERROR",
            file_count=0, dir_count=0, copilot_output=""
        )
        assert "## Copilot Output" in md2
        assert "## Execution Log" in md2
        
        # Test multiline with special chars
        special_output = """Line 1
Special chars: <>&"'
Unicode: 日本語"""
        
        collector3 = SessionLogCollector("test3")
        md3 = collector3.get_markdown(
            prompt="Test", model="gpt-4", status="COMPLETED",
            file_count=1, dir_count=1, copilot_output=special_output
        )
        assert "Line 1" in md3
        assert 'Special chars: <>&"\'' in md3
        assert "Unicode: 日本語" in md3
