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
    BASE_DIR,
    PROMPT_LOG_TRUNCATE_LENGTH,
    PROMPT_SUMMARY_TRUNCATE_LENGTH,
    UNIQUE_ID_LENGTH,
    PROGRESS_LOG_INTERVAL_SECONDS,
    init_config,
    is_initialized,
    get_prompt_template,
    CONFIG_YAML_PATH
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
    
    def test_prompt_truncate_lengths(self):
        """Test that prompt truncation lengths are positive."""
        assert PROMPT_LOG_TRUNCATE_LENGTH > 0
        assert PROMPT_LOG_TRUNCATE_LENGTH == 100
        assert PROMPT_SUMMARY_TRUNCATE_LENGTH > 0
        assert PROMPT_SUMMARY_TRUNCATE_LENGTH == 200
    
    def test_unique_id_length(self):
        """Test that unique ID length is positive."""
        assert UNIQUE_ID_LENGTH > 0
        assert UNIQUE_ID_LENGTH == 8
    
    def test_progress_log_interval(self):
        """Test that progress log interval is positive."""
        assert PROGRESS_LOG_INTERVAL_SECONDS > 0
        assert PROGRESS_LOG_INTERVAL_SECONDS == 30


class TestConfigInitialization:
    """Tests for configuration initialization."""
    
    def test_init_config_can_be_called(self):
        """Test that init_config can be called without error."""
        # Should not raise any exceptions
        init_config()
    
    def test_init_config_is_idempotent(self):
        """Test that init_config can be called multiple times safely."""
        init_config()
        init_config()
        init_config()
        # Should not raise any exceptions
    
    def test_is_initialized_returns_bool(self):
        """Test that is_initialized returns a boolean."""
        result = is_initialized()
        assert isinstance(result, bool)


class TestPromptTemplates:
    """Tests for prompt template functionality."""
    
    def test_config_yaml_path_exists(self):
        """Test that CONFIG_YAML_PATH is a Path object."""
        assert isinstance(CONFIG_YAML_PATH, Path)
    
    def test_get_prompt_template_returns_string(self):
        """Test that get_prompt_template returns a string."""
        # After init_config, templates should be loaded
        init_config()
        result = get_prompt_template('createproject')
        assert isinstance(result, str)
    
    def test_get_prompt_template_unknown_command(self):
        """Test that get_prompt_template returns empty string for unknown commands."""
        init_config()
        result = get_prompt_template('nonexistent_command')
        assert result == ""
    
    def test_get_prompt_template_createproject_has_content(self):
        """Test that createproject template has content when config.yaml exists."""
        init_config()
        if CONFIG_YAML_PATH.exists():
            result = get_prompt_template('createproject')
            # Template should have content if config.yaml exists
            assert len(result) > 0
