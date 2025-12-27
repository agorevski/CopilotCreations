"""
Configuration settings for the Discord Copilot Bot.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Discord Configuration
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")

# Project Paths
BASE_DIR = Path(__file__).parent.parent
PROJECTS_DIR = BASE_DIR / "projects"
PROJECTS_DIR.mkdir(exist_ok=True)

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
