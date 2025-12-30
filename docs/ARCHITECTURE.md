# Discord Copilot Bot - Architecture

## Overview

The Discord Copilot Bot is a Discord bot that executes the `copilot-cli` tool to create projects based on user prompts. It provides real-time feedback on project creation progress through Discord messages and optionally integrates with GitHub to automatically create repositories.

## Project Structure

```
CopilotCreations/
├── run.py                 # Application entry point
├── requirements.txt       # Python dependencies
├── config.yaml           # Prompt templates for commands
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
│   │   ├── createproject.py   # /createproject command handler
│   │   └── session_commands.py # /startproject, /buildproject, /cancelprompt
│   │
│   └── utils/            # Utility modules
│       ├── __init__.py
│       ├── logging.py        # Logging and session log collector
│       ├── folder_utils.py   # Folder tree and ignore pattern utilities
│       ├── text_utils.py     # Text manipulation utilities
│       ├── github.py         # GitHub integration utilities
│       ├── naming.py         # AI-powered repository naming
│       ├── async_buffer.py   # Thread-safe async output buffer
│       ├── session_manager.py    # User session tracking for prompt building
│       ├── prompt_refinement.py  # AI-assisted prompt refinement service
│       └── process_registry.py   # Subprocess tracking and cleanup
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
│   ├── test_naming.py
│   ├── test_process_registry.py
│   ├── test_prompt_refinement.py
│   ├── test_session_manager.py
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

### Prompt Configuration (`config.yaml`)

YAML file containing prompt templates that are prepended to user prompts:
- **`createproject`** - Template prepended to `/createproject` prompts
  - Defines professional project requirements (CI/CD, tests, documentation)
  - Specifies expected directory structure
  - Sets quality standards (e.g., 75% test coverage)
- **`prompt_refinement_system`** - System prompt for AI-assisted prompt refinement
  - Systematic 4-round questioning strategy covering 14 areas
  - Produces exhaustive 12-section project specifications
  - Anti-vagueness rules ensure explicit, actionable requirements
- **`repository_naming_prompt`** - Prompt for generating creative repo names
- **`repository_description_prompt`** - Prompt for generating repo descriptions

### Configuration (`src/config.py`)

Centralized configuration with explicit initialization:
- **`init_config()`** - Must be called at startup to:
  - Create `PROJECTS_DIR` directory
  - Load prompt templates from `config.yaml`
  - Set initialization flag
- Environment variables are loaded via `load_dotenv()` at module import time
- **`is_initialized()`** - Check if config has been initialized
- Discord bot token
- GitHub integration settings (`GITHUB_ENABLED`, `GITHUB_TOKEN`, `GITHUB_USERNAME`, `GITHUB_REPO_PRIVATE`)
- Cleanup settings (`CLEANUP_AFTER_PUSH`)
- Project paths
- Timeout settings
- Message length limits (`MAX_FOLDER_STRUCTURE_LENGTH`, `MAX_COPILOT_OUTPUT_LENGTH`, `MAX_SUMMARY_LENGTH`)
- Parallelism settings (`MAX_PARALLEL_REQUESTS`)
- Copilot CLI default flags
- Prompt truncation lengths (`PROMPT_LOG_TRUNCATE_LENGTH`, `PROMPT_SUMMARY_TRUNCATE_LENGTH`)
- Unique ID generation settings (`UNIQUE_ID_LENGTH`)
- Progress logging interval (`PROGRESS_LOG_INTERVAL_SECONDS`)
- Input validation (`MAX_PROMPT_LENGTH`, `MODEL_NAME_PATTERN`)
- Azure OpenAI settings (`AZURE_OPENAI_API_VERSION`)

### Commands (`src/commands/`)

#### `/createproject` Command

The main command is organized into modular helper functions:

**Section Generator Functions:**
- `_generate_folder_structure_section()` - Generates folder tree, truncated to 750 chars
- `_generate_copilot_output_section()` - Generates copilot output, truncated to 2500 chars
- `_generate_summary_section()` - Generates summary with status, prompt, model, stats, and GitHub URL
- `_build_unified_message()` - Combines all three sections into a single message

**Helper Functions:**
- `_create_project_directory()` - Creates unique project folder
- `_send_initial_message()` - Sends single unified Discord message for progress tracking
- `_run_copilot_process()` - Executes copilot CLI with timeout handling
- `_update_final_message()` - Updates unified message with final state
- `_handle_github_integration()` - Creates GitHub repo and pushes code

**Input Validation:**
- Empty prompts are rejected
- Prompts exceeding `MAX_PROMPT_LENGTH` (10,000 chars) are rejected
- Model names are validated against `MODEL_NAME_PATTERN`

**Shared Utilities:**
- `update_unified_message()` - Updates all three sections in a single message every 3 seconds
- `read_stream()` - Reads process output to async buffer

#### Session Commands (`/startproject`, `/buildproject`, `/cancelprompt`)

Conversational prompt-building commands:

**`/startproject`:**
- Starts a new prompt-building session
- Tracks all user messages and bot responses
- Uses AI to ask clarifying questions (if Azure OpenAI configured)

**`/buildproject`:**
- Finalizes the session and generates project
- Deletes all session messages from the channel (requires Manage Messages permission)
- Uses AI to produce exhaustive 12-section specification
- Reuses `_execute_project_creation()` for actual project generation

**`/cancelprompt`:**
- Cancels active session and discards collected messages

**Message Listener:**
- Captures user messages during active sessions
- Tracks message IDs for cleanup on build
- Sends AI responses with clarifying questions

### Utilities (`src/utils/`)

#### `session_manager.py`
- `PromptSession` dataclass - Tracks user session state
  - `messages` - User messages collected during session
  - `conversation_history` - Full conversation for AI context
  - `message_ids` - Discord message IDs for cleanup on build
  - `refined_prompt` - Final AI-generated specification
- `SessionManager` class - Manages active sessions
  - Start/end/get sessions by user+channel
  - Automatic session expiry after timeout
  - Background cleanup task for expired sessions

#### `prompt_refinement.py`
- `PromptRefinementService` class - AI-assisted prompt refinement
  - Uses Azure OpenAI for conversational refinement
  - Systematic questioning across 14 areas in 4 rounds
  - Generates exhaustive 12-section project specifications
  - Anti-vagueness rules ensure explicit requirements

#### `naming.py`
- `generate_creative_name()` - AI-powered repository naming
- `generate_description()` - AI-powered repository descriptions

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

#### `process_registry.py`
- `ProcessRegistry`: Class for tracking and cleaning up subprocesses
  - `register()`: Register a subprocess for tracking
  - `unregister()`: Remove a subprocess from tracking
  - `kill_all()`: Async method to kill all tracked subprocesses
  - `kill_all_sync()`: Sync method for signal handlers
  - `active_count`: Property returning number of tracked processes
- `get_process_registry()`: Get or create the global singleton instance

## Data Flow

### Quick Project Creation (`/createproject`)

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
│  Send Initial Message   │
│  _send_initial_message()│
│  (single unified msg)   │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│  Run Copilot Process    │
│  _run_copilot_process() │
│  (uses AsyncOutputBuffer)
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│  Update Unified Message │
│  update_unified_message()│
│  (every 3 seconds)      │
│  ┌───────────────────┐  │
│  │ Folder Structure  │  │
│  │ (max 750 chars)   │  │
│  ├───────────────────┤  │
│  │ Copilot Output    │  │
│  │ (max 2500 chars)  │  │
│  ├───────────────────┤  │
│  │ Summary Section   │  │
│  │ (status, stats)   │  │
│  └───────────────────┘  │
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
│  Update Final Message   │
│  _update_final_message()│
└─────────────────────────┘
```

### Conversational Project Creation (`/startproject` → `/buildproject`)

```
User sends /startproject
        │
        ▼
┌─────────────────────────┐
│  Create Session         │
│  SessionManager         │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│  AI Asks Questions      │◄──────────┐
│  PromptRefinementService│           │
└───────────┬─────────────┘           │
            │                         │
            ▼                         │
┌─────────────────────────┐           │
│  User Sends Messages    │           │
│  (tracked in session)   │───────────┘
└───────────┬─────────────┘    (repeat 2-4 rounds)
            │
            ▼
User sends /buildproject
        │
        ▼
┌─────────────────────────┐
│  Generate Final Spec    │
│  (12-section format)    │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│  Delete Session Messages│
│  (cleanup chat)         │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│  Execute Project Creation│
│  (same as /createproject)│
└─────────────────────────┘
```

## Key Features

### Real-time Updates
- **Unified message** with folder structure, copilot output, and summary
- Updates every 3 seconds (configurable via `UPDATE_INTERVAL`)
- Only sends updates when content changes (rate limit friendly)
- Each section has character limits:
  - Folder structure: 400 characters (truncated with ellipsis)
  - Copilot output: 800 characters (truncated from start)
  - Summary: 500 characters with status, stats, and GitHub URL

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
- Logs are kept internally for debugging
- Status information displayed in unified message

### Chat Cleanup
- Session messages (user + bot) are tracked by ID
- All messages deleted when `/buildproject` runs
- Requires **Manage Messages** permission
- Graceful fallback if permission denied

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
Configuration directories and templates are set up via `init_config()` at startup:
- Directory creation happens explicitly, not at import time
- Prompt templates loaded from config.yaml
- Environment variables loaded via `load_dotenv()` at import (safe operation)
- Clear initialization sequence in `run.py`

### DRY (Don't Repeat Yourself)
Common patterns are extracted into reusable functions:
- Section generator functions for unified message (`_generate_folder_structure_section()`, etc.)
- Helper functions for each distinct responsibility

### Single Responsibility
Long functions are broken into focused helper functions:
- Each function does one thing well
- Easier to test individual components
- Better code organization and readability

### Unified Message Format
The progress message uses a structured format:
```
```
📁 project_folder/
├── file1.txt
└── subdir/
```
```
(copilot output here, max 2500 chars)
```
📋 Summary
Status: 🔄 **IN PROGRESS**
Prompt: user prompt here...
Model: default
Files: 5 | Dirs: 2
User: username
```
