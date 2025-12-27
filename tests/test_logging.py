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
