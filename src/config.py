"""
Configuration settings for the Discord Copilot Bot.
"""

import os
from pathlib import Path

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

# Project Paths
BASE_DIR = Path(__file__).parent.parent
PROJECTS_DIR = BASE_DIR / "projects"


def init_config() -> None:
    """Initialize configuration by creating required directories.
    
    This function should be called once at application startup.
    It's safe to call multiple times.
    """
    global _initialized
    
    if _initialized:
        return
    
    # Create projects directory
    PROJECTS_DIR.mkdir(exist_ok=True)
    
    _initialized = True


def is_initialized() -> bool:
    """Check if configuration has been initialized."""
    return _initialized

# Timeout Configuration
TIMEOUT_SECONDS = 30 * 60  # 30 minutes

# Discord Message Configuration
UPDATE_INTERVAL = 1  # seconds - check for changes every second
MAX_MESSAGE_LENGTH = 4000  # Discord max is 4000 for bot messages

# Copilot CLI Configuration
COPILOT_DEFAULT_FLAGS = [
    "--allow-all-paths",
    "--allow-all-tools",
    "--allow-all-urls"
]

# Prompt truncation lengths for display
PROMPT_LOG_TRUNCATE_LENGTH = 100
PROMPT_SUMMARY_TRUNCATE_LENGTH = 200

# Unique ID generation
UNIQUE_ID_LENGTH = 8

# Progress logging interval in seconds
PROGRESS_LOG_INTERVAL_SECONDS = 30
