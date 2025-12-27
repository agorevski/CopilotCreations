"""
Tests for configuration module.
"""

import pytest
from pathlib import Path

from src.config import (
    PROJECTS_DIR,
    TIMEOUT_SECONDS,
    UPDATE_INTERVAL,
    MAX_MESSAGE_LENGTH,
    COPILOT_DEFAULT_FLAGS,
    BASE_DIR
)


class TestConfig:
    """Tests for configuration values."""
    
    def test_projects_dir_is_path(self):
        """Test that PROJECTS_DIR is a Path object."""
        assert isinstance(PROJECTS_DIR, Path)
    
    def test_base_dir_is_path(self):
        """Test that BASE_DIR is a Path object."""
        assert isinstance(BASE_DIR, Path)
    
    def test_timeout_is_positive(self):
        """Test that timeout is a positive number."""
        assert TIMEOUT_SECONDS > 0
        assert TIMEOUT_SECONDS == 30 * 60  # 30 minutes
    
    def test_update_interval_is_positive(self):
        """Test that update interval is positive."""
        assert UPDATE_INTERVAL > 0
        assert UPDATE_INTERVAL == 1
    
    def test_max_message_length(self):
        """Test that max message length is set correctly."""
        assert MAX_MESSAGE_LENGTH > 0
        assert MAX_MESSAGE_LENGTH == 4000
    
    def test_copilot_default_flags(self):
        """Test that default flags are set."""
        assert isinstance(COPILOT_DEFAULT_FLAGS, list)
        assert len(COPILOT_DEFAULT_FLAGS) > 0
        assert "--allow-all-paths" in COPILOT_DEFAULT_FLAGS
        assert "--allow-all-tools" in COPILOT_DEFAULT_FLAGS
        assert "--allow-all-urls" in COPILOT_DEFAULT_FLAGS
