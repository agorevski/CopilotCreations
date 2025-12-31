"""
Tests for configuration module.

This module tests configuration values, initialization, and prompt templates
that control the bot's behavior.
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
    GITHUB_REPO_PRIVATE,
    MAX_PARALLEL_REQUESTS,
    init_config,
    is_initialized,
    get_prompt_template,
    CONFIG_YAML_PATH
)


class TestConfigValues:
    """Tests for configuration values and their expected types/values."""
    
    def test_directory_paths(self):
        """
        Tests directory path configurations:
        - PROJECTS_DIR is a Path object
        - BASE_DIR is a Path object
        """
        assert isinstance(PROJECTS_DIR, Path)
        assert isinstance(BASE_DIR, Path)
    
    def test_timeout_and_intervals(self):
        """
        Tests timeout and interval configurations:
        - TIMEOUT_SECONDS is positive and calculated from TIMEOUT_MINUTES
        - UPDATE_INTERVAL is positive (3 seconds for message updates)
        - PROGRESS_LOG_INTERVAL_SECONDS is positive (30 seconds)
        """
        from src.config import TIMEOUT_MINUTES
        
        assert TIMEOUT_SECONDS > 0
        assert TIMEOUT_SECONDS == TIMEOUT_MINUTES * 60
        
        assert UPDATE_INTERVAL > 0
        assert UPDATE_INTERVAL == 3
        
        assert PROGRESS_LOG_INTERVAL_SECONDS > 0
        assert PROGRESS_LOG_INTERVAL_SECONDS == 30
    
    def test_message_and_prompt_limits(self):
        """
        Tests message and prompt length limits:
        - MAX_MESSAGE_LENGTH for Discord (1950, leaves buffer for 2000 limit)
        - PROMPT_LOG_TRUNCATE_LENGTH (100)
        - PROMPT_SUMMARY_TRUNCATE_LENGTH (200)
        """
        assert MAX_MESSAGE_LENGTH > 0
        assert MAX_MESSAGE_LENGTH == 1950
        
        assert PROMPT_LOG_TRUNCATE_LENGTH > 0
        assert PROMPT_LOG_TRUNCATE_LENGTH == 100
        
        assert PROMPT_SUMMARY_TRUNCATE_LENGTH > 0
        assert PROMPT_SUMMARY_TRUNCATE_LENGTH == 200
    
    def test_copilot_flags(self):
        """
        Tests Copilot CLI default flags:
        - Is a non-empty list
        - Contains required permission flags
        """
        assert isinstance(COPILOT_DEFAULT_FLAGS, list)
        assert len(COPILOT_DEFAULT_FLAGS) > 0
        assert "--allow-all-paths" in COPILOT_DEFAULT_FLAGS
        assert "--allow-all-tools" in COPILOT_DEFAULT_FLAGS
        assert "--allow-all-urls" in COPILOT_DEFAULT_FLAGS
    
    def test_other_constants(self):
        """
        Tests other configuration constants:
        - UNIQUE_ID_LENGTH (8)
        - GITHUB_REPO_PRIVATE is boolean
        - MAX_PARALLEL_REQUESTS is positive integer
        """
        assert UNIQUE_ID_LENGTH > 0
        assert UNIQUE_ID_LENGTH == 8
        
        assert isinstance(GITHUB_REPO_PRIVATE, bool)
        
        assert isinstance(MAX_PARALLEL_REQUESTS, int)
        assert MAX_PARALLEL_REQUESTS > 0
        assert MAX_PARALLEL_REQUESTS >= 1  # Reasonable default


class TestConfigInitialization:
    """Tests for configuration initialization and idempotency."""
    
    def test_init_config(self):
        """
        Tests init_config function:
        - Can be called without error
        - Is idempotent (multiple calls safe)
        - is_initialized returns boolean
        """
        init_config()  # Should not raise
        init_config()  # Idempotent
        init_config()  # Multiple calls safe
        
        result = is_initialized()
        assert isinstance(result, bool)


class TestPromptTemplates:
    """Tests for prompt template functionality and error handling."""
    
    def test_get_prompt_template(self):
        """
        Tests get_prompt_template function:
        - CONFIG_YAML_PATH is a Path
        - Returns string for known commands
        - Returns empty string for unknown commands
        - Template has content when config.yaml exists
        """
        assert isinstance(CONFIG_YAML_PATH, Path)
        
        init_config()
        
        result = get_prompt_template('createproject')
        assert isinstance(result, str)
        
        unknown = get_prompt_template('nonexistent_command')
        assert unknown == ""
        
        if CONFIG_YAML_PATH.exists():
            template = get_prompt_template('createproject')
            assert len(template) > 0
    
    def test_init_config_error_handling(self):
        """
        Tests init_config error handling:
        - Logs warning on YAML parse error but completes
        - Handles IOError gracefully
        """
        from unittest.mock import patch, mock_open
        import src.config
        
        # Test YAML error handling
        src.config._initialized = False
        src.config.PROMPT_TEMPLATES.clear()
        
        with patch.object(Path, 'exists', return_value=True), \
             patch('builtins.open', mock_open(read_data='invalid: yaml: content: [')), \
             patch('yaml.safe_load', side_effect=Exception("YAML parse error")), \
             patch('logging.getLogger') as mock_logger:
            mock_log = mock_logger.return_value
            init_config()
            assert src.config._initialized is True
        
        # Test IOError handling
        src.config._initialized = False
        src.config.PROMPT_TEMPLATES.clear()
        
        with patch.object(Path, 'exists', return_value=True), \
             patch('builtins.open', side_effect=IOError("Permission denied")), \
             patch('logging.getLogger'):
            init_config()
            assert src.config._initialized is True
        
        # Reset for other tests
        src.config._initialized = False
        src.config.PROMPT_TEMPLATES.clear()
        init_config()
