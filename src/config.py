"""
Configuration settings for the Discord Copilot Bot.
"""

import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

# Load environment variables (safe - just reads .env file)
load_dotenv()

# Track initialization state for directory creation
_initialized = False

# Discord Configuration
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")

# GitHub Integration Configuration
GITHUB_ENABLED = os.getenv("GITHUB_ENABLED", "false").lower() == "true"
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_USERNAME = os.getenv("GITHUB_USERNAME")

# Cleanup Configuration - delete local project folder after successful GitHub push
CLEANUP_AFTER_PUSH = os.getenv("CLEANUP_AFTER_PUSH", "true").lower() == "true"

# Project Paths
BASE_DIR = Path(__file__).parent.parent
PROJECTS_DIR = BASE_DIR / "projects"
CONFIG_YAML_PATH = BASE_DIR / "config.yaml"

# Prompt templates loaded from config.yaml
PROMPT_TEMPLATES: dict = {}


def init_config() -> None:
    """Initialize configuration by creating required directories and loading config.yaml.
    
    This function should be called once at application startup.
    It's safe to call multiple times.
    """
    global _initialized, PROMPT_TEMPLATES
    
    if _initialized:
        return
    
    # Create projects directory
    PROJECTS_DIR.mkdir(exist_ok=True)
    
    # Load prompt templates from config.yaml
    if CONFIG_YAML_PATH.exists():
        try:
            with open(CONFIG_YAML_PATH, 'r', encoding='utf-8') as f:
                PROMPT_TEMPLATES.update(yaml.safe_load(f) or {})
        except Exception:
            pass  # Silently ignore config.yaml errors, use empty templates
    
    _initialized = True


def get_prompt_template(command_name: str) -> str:
    """Get the prompt template for a specific command.
    
    Args:
        command_name: The name of the command (e.g., 'createproject')
        
    Returns:
        The prompt template string, or empty string if not found.
    """
    return PROMPT_TEMPLATES.get(command_name, "")


def is_initialized() -> bool:
    """Check if configuration has been initialized."""
    return _initialized

# Timeout Configuration
TIMEOUT_MINUTES = int(os.getenv("TIMEOUT_MINUTES", "30"))
TIMEOUT_SECONDS = TIMEOUT_MINUTES * 60

# Discord Message Configuration
UPDATE_INTERVAL = 1  # seconds - check for changes every second
MAX_MESSAGE_LENGTH = 4000  # Discord max is 4000 for bot messages

# Copilot CLI Configuration
COPILOT_DEFAULT_FLAGS = [
    "--allow-all-paths",
    "--allow-all-tools",
    "--allow-all-urls",
    "--log-level", "debug"
]

# Prompt truncation lengths for display
PROMPT_LOG_TRUNCATE_LENGTH = 100
PROMPT_SUMMARY_TRUNCATE_LENGTH = 200

# Unique ID generation
UNIQUE_ID_LENGTH = 8

# Progress logging interval in seconds
PROGRESS_LOG_INTERVAL_SECONDS = 30

# Input validation
MAX_PROMPT_LENGTH = 10000
MODEL_NAME_PATTERN = r'^[a-zA-Z0-9\-_.]+$'
