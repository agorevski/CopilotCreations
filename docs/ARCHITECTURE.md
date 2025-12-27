# Discord Copilot Bot - Architecture

## Overview

The Discord Copilot Bot is a Discord bot that executes the `copilot-cli` tool to create projects based on user prompts. It provides real-time feedback on project creation progress through Discord messages and optionally integrates with GitHub to automatically create repositories.

## Project Structure

```
CopilotCreations/
├── run.py                 # Application entry point
├── requirements.txt       # Python dependencies
├── .env                   # Environment variables (not in git)
├── .env.example          # Example environment file
├── .folderignore         # Patterns for folders to collapse in tree view
├── .gitignore            # Git ignore patterns
│
├── src/                   # Source code
│   ├── __init__.py       # Package marker with version
│   ├── bot.py            # Discord bot client
│   ├── config.py         # Configuration settings
│   │
│   ├── commands/         # Discord slash commands
│   │   ├── __init__.py
│   │   └── createproject.py  # /createproject command handler
│   │
│   └── utils/            # Utility modules
│       ├── __init__.py
│       ├── logging.py    # Logging and session log collector
│       ├── folder_utils.py   # Folder tree and ignore pattern utilities
│       ├── text_utils.py # Text manipulation utilities
│       └── github.py     # GitHub integration utilities
│
├── tests/                # Test suite
│   ├── __init__.py
│   ├── test_folder_utils.py
│   ├── test_text_utils.py
│   └── test_logging.py
│
├── docs/                 # Documentation
│   ├── ARCHITECTURE.md   # This file
│   └── USAGE.md          # User guide
│
└── projects/             # Generated projects directory (gitignored)
```

## Components

### Entry Point (`run.py`)

The main entry point that:
- Imports the bot instance
- Sets up commands
- Starts the bot

### Bot Client (`src/bot.py`)

The Discord bot client class:
- Extends `discord.Client`
- Manages the command tree for slash commands
- Handles the `on_ready` event

### Configuration (`src/config.py`)

Centralized configuration including:
- Discord bot token
- GitHub integration settings (`GITHUB_ENABLED`, `GITHUB_TOKEN`, `GITHUB_USERNAME`)
- Project paths
- Timeout settings
- Message length limits
- Copilot CLI default flags
- Prompt truncation lengths (`PROMPT_LOG_TRUNCATE_LENGTH`, `PROMPT_SUMMARY_TRUNCATE_LENGTH`)
- Unique ID generation settings (`UNIQUE_ID_LENGTH`)
- Progress logging interval (`PROGRESS_LOG_INTERVAL_SECONDS`)

### Commands (`src/commands/`)

#### `/createproject` Command

The main command that:
1. Creates a unique project folder
2. Spawns the `copilot-cli` process
3. Updates Discord messages with real-time progress
4. Generates a log file upon completion
5. Optionally creates a GitHub repository and pushes project files

### Utilities (`src/utils/`)

#### `logging.py`
- `setup_logging()`: Configures the application logger
- `SessionLogCollector`: Collects logs for a specific command session

#### `folder_utils.py`
- `sanitize_username()`: Makes usernames safe for file paths
- `load_folderignore()`: Loads `.folderignore` patterns
- `is_ignored()`: Checks if a path matches ignore patterns
- `count_files_recursive()`: Counts files in a directory
- `count_files_excluding_ignored()`: Counts files excluding ignored folders
- `get_folder_tree()`: Generates a visual folder tree

#### `text_utils.py`
- `truncate_output()`: Truncates text to fit Discord message limits

#### `github.py`
- `GitHubManager`: Class that manages GitHub repository operations
  - `is_configured()`: Checks if GitHub integration is properly configured
  - `copy_gitignore()`: Copies the root `.gitignore` to project directories
  - `create_repository()`: Creates a new GitHub repository
  - `init_and_push()`: Initializes git and pushes to GitHub
  - `create_and_push_project()`: Complete workflow for GitHub integration
- `github_manager`: Singleton instance for easy access

## Data Flow

```
User sends /createproject command
        │
        ▼
┌─────────────────────────┐
│   Command Handler       │
│   (createproject.py)    │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│  Create Project Folder  │
│  Initialize Logger      │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│  Spawn copilot-cli      │
│  Process                │
└───────────┬─────────────┘
            │
      ┌─────┴─────┐
      ▼           ▼
┌──────────┐ ┌──────────────┐
│  Update  │ │   Update     │
│  Tree    │ │   Output     │
│  Message │ │   Message    │
└────┬─────┘ └──────┬───────┘
     │              │
     └──────┬───────┘
            │
            ▼
┌─────────────────────────┐
│  Process Completes      │
│  Generate Summary       │
│  Attach Log File        │
└───────────┬─────────────┘
            │
            ▼ (if GitHub enabled)
┌─────────────────────────┐
│  GitHub Integration     │
│  - Copy .gitignore      │
│  - Create repository    │
│  - Init git & push      │
└─────────────────────────┘
```

## Key Features

### Real-time Updates
- File tree and output messages update every 1 second
- Only sends updates when content changes (rate limit friendly)

### Folder Ignore Patterns
- `.folderignore` file works like `.gitignore`
- Ignored folders show as collapsed with file count
- Reduces clutter in folder tree display

### Session Logging
- Each command session has its own log collector
- Logs are attached as markdown files to the summary message
- Includes timing, status, and full execution log

### Error Handling
- Graceful handling of timeouts (30 minute limit)
- Error messages displayed in Discord
- Fallback mechanisms for failed operations
- **All exceptions are logged** - no silent exception swallowing; errors are logged at appropriate levels (debug for HTTP errors, warning for unexpected errors)

### GitHub Integration
- **Optional feature** - Disabled by default, enable via `GITHUB_ENABLED=true` in `.env`
- **Automatic .gitignore** - Copies root `.gitignore` to each project to keep repositories clean
- **Private repositories** - All created repositories are private by default
- **Authenticated push** - Uses Personal Access Token for secure git operations
- **Graceful degradation** - If GitHub integration fails, project creation still succeeds
