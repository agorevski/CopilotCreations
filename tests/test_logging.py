"""
Tests for logging utilities.
"""

import pytest

from src.utils.logging import SessionLogCollector


class TestSessionLogCollector:
    """Tests for SessionLogCollector class."""
    
    def test_init(self):
        collector = SessionLogCollector("test_session")
        assert collector.session_id == "test_session"
        assert collector.logs == []
    
    def test_info_log(self):
        collector = SessionLogCollector("test")
        collector.info("Test message")
        assert len(collector.logs) == 1
        assert "INFO" in collector.logs[0]
        assert "Test message" in collector.logs[0]
    
    def test_warning_log(self):
        collector = SessionLogCollector("test")
        collector.warning("Warning message")
        assert len(collector.logs) == 1
        assert "WARNING" in collector.logs[0]
    
    def test_error_log(self):
        collector = SessionLogCollector("test")
        collector.error("Error message")
        assert len(collector.logs) == 1
        assert "ERROR" in collector.logs[0]
    
    def test_multiple_logs(self):
        collector = SessionLogCollector("test")
        collector.info("First")
        collector.warning("Second")
        collector.error("Third")
        assert len(collector.logs) == 3
    
    def test_get_markdown(self):
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
        # Copilot Output section should exist even when empty
        assert "## Copilot Output" in md
    
    def test_get_markdown_with_copilot_output(self):
        """Test that copilot output is included in the markdown log."""
        collector = SessionLogCollector("test_session")
        collector.info("Starting copilot process...")
        
        copilot_output = """Creating project structure...
Generating main.py...
Generating requirements.txt...
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
        assert "Generating main.py..." in md
        assert "Generating requirements.txt..." in md
        assert "Done! Created 3 files." in md
    
    def test_get_markdown_copilot_output_empty(self):
        """Test markdown generation when copilot output is empty."""
        collector = SessionLogCollector("test_session")
        
        md = collector.get_markdown(
            prompt="Test prompt",
            model="default",
            status="ERROR",
            file_count=0,
            dir_count=0,
            copilot_output=""
        )
        
        assert "## Copilot Output" in md
        assert "## Execution Log" in md
    
    def test_get_markdown_copilot_output_multiline(self):
        """Test that multiline copilot output is preserved correctly."""
        collector = SessionLogCollector("test_session")
        
        multiline_output = """Line 1
Line 2
Line 3
Special chars: <>&"'
Unicode: 日本語"""
        
        md = collector.get_markdown(
            prompt="Test",
            model="gpt-4",
            status="COMPLETED",
            file_count=1,
            dir_count=1,
            copilot_output=multiline_output
        )
        
        assert "Line 1" in md
        assert "Line 2" in md
        assert "Line 3" in md
        assert 'Special chars: <>&"\'' in md
        assert "Unicode: 日本語" in md
