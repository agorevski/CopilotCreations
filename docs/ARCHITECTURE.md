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
│   ├── bot.py            # Discord bot client with factory pattern
│   ├── config.py         # Configuration settings with explicit init
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
│       ├── github.py     # GitHub integration utilities
│       └── async_buffer.py   # Thread-safe async output buffer
│
├── tests/                # Test suite
│   ├── __init__.py
│   ├── test_async_buffer.py
│   ├── test_bot.py
│   ├── test_config.py
│   ├── test_createproject.py
│   ├── test_folder_utils.py
│   ├── test_github.py
│   ├── test_logging.py
│   └── test_text_utils.py
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
- Calls `init_config()` to load environment and create directories
- Gets bot instance via `get_bot()` factory function
- Sets up commands
- Starts the bot

### Bot Client (`src/bot.py`)

The Discord bot client module provides:
- `CopilotBot` class extending `discord.Client`
- **Factory Functions:**
  - `get_bot()` - Returns singleton bot instance
  - `create_bot()` - Creates new instance (for testing)
  - `reset_bot()` - Resets singleton (for testing)
- **Graceful Shutdown:**
  - `setup_signal_handlers()` - Registers SIGINT/SIGTERM handlers
  - `cleanup()` - Async cleanup method for resources
- `on_ready_handler()` - Handles bot ready event
- `run_bot()` - Main entry point to start the bot

### Configuration (`src/config.py`)

Centralized configuration with explicit initialization:
- **`init_config()`** - Must be called at startup to:
  - Load `.env` file via `load_dotenv()`
  - Create `PROJECTS_DIR` directory
  - Set configuration variables
- **`is_initialized()`** - Check if config has been initialized
- Discord bot token
- GitHub integration settings (`GITHUB_ENABLED`, `GITHUB_TOKEN`, `GITHUB_USERNAME`)
- Project paths
- Timeout settings
- Message length limits
- Copilot CLI default flags
- Prompt truncation lengths (`PROMPT_LOG_TRUNCATE_LENGTH`, `PROMPT_SUMMARY_TRUNCATE_LENGTH`)
- Unique ID generation settings (`UNIQUE_ID_LENGTH`)
- Progress logging interval (`PROGRESS_LOG_INTERVAL_SECONDS`)
- Input validation (`MAX_PROMPT_LENGTH`, `MODEL_NAME_PATTERN`)

### Commands (`src/commands/`)

#### `/createproject` Command

The main command is organized into modular helper functions:

**Helper Functions:**
- `_create_project_directory()` - Creates unique project folder
- `_send_initial_messages()` - Sends Discord messages for progress tracking
- `_run_copilot_process()` - Executes copilot CLI with timeout handling
- `_update_final_messages()` - Updates Discord messages with final state
- `_handle_github_integration()` - Creates GitHub repo and pushes code
- `_send_summary()` - Sends final summary with log attachment

**Input Validation:**
- Empty prompts are rejected
- Prompts exceeding `MAX_PROMPT_LENGTH` (10,000 chars) are rejected
- Model names are validated against `MODEL_NAME_PATTERN`

**Shared Utilities:**
- `update_message_with_content()` - Generic message updater (DRY pattern)
- `update_file_tree_message()` - Updates file tree display
- `update_output_message()` - Updates command output display
- `read_stream()` - Reads process output to async buffer

### Utilities (`src/utils/`)

#### `async_buffer.py`
- `AsyncOutputBuffer` class - Thread-safe buffer for concurrent async operations
  - Uses `asyncio.Lock` for atomic operations
  - `append()` / `get_content()` - Async methods
  - `append_sync()` / `get_content_sync()` - Sync fallbacks

#### `logging.py`
- `get_logger()`: Returns the singleton application logger (preferred)
- `setup_logging()`: Configures and returns the logger (deprecated, kept for backward compatibility)
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
- `format_error_message()`: Formats error messages consistently for Discord

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
│  _create_project_directory()
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│  Send Initial Messages  │
│  _send_initial_messages()
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│  Run Copilot Process    │
│  _run_copilot_process() │
│  (uses AsyncOutputBuffer)
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
│  Update Final Messages  │
│  _update_final_messages()
└───────────┬─────────────┘
            │
            ▼ (if GitHub enabled)
┌─────────────────────────┐
│  GitHub Integration     │
│  _handle_github_integration()
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│  Send Summary           │
│  _send_summary()        │
└─────────────────────────┘
```

## Key Features

### Real-time Updates
- File tree and output messages update every 1 second
- Only sends updates when content changes (rate limit friendly)

### Thread-Safe Operations
- `AsyncOutputBuffer` provides atomic append and read operations
- Uses `asyncio.Lock` to prevent race conditions
- Safe for concurrent access from multiple async tasks

### Graceful Shutdown
- Signal handlers for SIGINT and SIGTERM
- Clean resource cleanup before exit
- Proper Discord connection termination

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

## Design Patterns

### Factory Pattern
Bot instances are created via factory functions (`get_bot()`, `create_bot()`) rather than direct instantiation, enabling:
- Better testability with isolated instances
- Singleton management for production use
- Easy reset for test cleanup

### Explicit Initialization
Configuration is loaded via `init_config()` at startup rather than at import time:
- No side effects during module import
- Easier testing without unwanted file I/O
- Clear initialization sequence in `run.py`

### DRY (Don't Repeat Yourself)
Common patterns are extracted into reusable functions:
- `update_message_with_content()` for generic message updates
- Helper functions for each distinct responsibility

### Single Responsibility
Long functions are broken into focused helper functions:
- Each function does one thing well
- Easier to test individual components
- Better code organization and readability
