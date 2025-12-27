# Discord Copilot Bot

A Discord bot that executes `copilot-cli` to create projects based on user prompts.

## Features

- `/createproject prompt:<prompt> [model:<model>]` - Create a new project using Copilot CLI
- Real-time file tree updates (every 5 seconds)
- Rolling output window showing last 2000 characters (every 3 seconds)
- 30-minute timeout protection
- Concurrent user support
- Full error handling with stack traces

## Architecture

```
CopilotCreations/
├── run.py                  # Application entry point
├── src/
│   ├── bot.py              # Discord bot client with app commands support
│   ├── config.py           # Configuration settings (env vars, paths, timeouts)
│   ├── commands/
│   │   └── createproject.py  # /createproject slash command implementation
│   └── utils/
│       ├── folder_utils.py   # File tree generation and directory utilities
│       ├── logging.py        # Logging configuration
│       └── text_utils.py     # Text formatting utilities
├── tests/                  # Unit tests for all modules
├── projects/               # Output directory for generated projects
└── docs/                   # Documentation
```

### Key Components

- **`run.py`**: Entry point that initializes the bot and registers commands
- **`src/bot.py`**: Discord client using `discord.py` with application commands
- **`src/config.py`**: Centralized configuration loaded from environment variables
- **`src/commands/createproject.py`**: Handles the `/createproject` command, spawns `copilot-cli`, and manages real-time Discord message updates
- **`src/utils/`**: Shared utilities for logging, file operations, and text processing

## Setup

1. **Install dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

2. **Configure environment:**

   ```bash
   cp .env.example .env
   # Edit .env and add your Discord bot token
   ```

3. **Create a Discord Bot:**
   - Go to the [Discord Developer Portal](https://discord.com/developers/applications)
   - Create a new application
   - Go to "Bot" section and create a bot
   - Copy the token and paste it in your `.env` file
   - Enable the following under "Privileged Gateway Intents" if needed
   - Go to "OAuth2" > "URL Generator"
     - Select scopes: `bot`, `applications.commands`
     - Select permissions: `Send Messages`, `Embed Links`, `Read Message History`
   - Use the generated URL to invite the bot to your server
   - Optionally, if you run the bot for the first time after you have the token, the output will show something like this in the console and you can navigate to that Invite URL to attach the Bot to your server.
   ```text
   2025-12-27 14:19:15 | INFO     | Bot is ready! Logged in as CopilotCreations#8330
   2025-12-27 14:19:15 | INFO     | Projects will be saved to: C:\GIT\agorevski\CopilotCreations\projects
   2025-12-27 14:19:15 | INFO     | Invite URL: https://discord.com/api/oauth2/authorize?client_id=xxxxxxxxxxxx&permissions=274877975552&scope=bot%20applications.commands
   ```


4. **Ensure Copilot CLI is available:**
   - The `copilot` command must be accessible in your PATH

## Usage

```bash
python run.py
```

### Commands

**`/createproject`**

- `prompt` (required): The prompt describing what project to create
- `model` (optional): The model to use (e.g., `gpt-4`, `claude-3-opus`)

Example:

```text
/createproject prompt:Create a REST API in Python using FastAPI with user authentication
/createproject prompt:Build a React todo app model:gpt-4
```

## Project Structure

Projects are saved to `./projects/<username>_<timestamp>_<guid>/`

## Output

The bot sends two messages that update in real-time:

1. **File Tree** - Shows the current folder structure (updates every 5 seconds)
2. **Copilot Output** - Shows the last 2000 characters of output (updates every 3 seconds)

After completion, a summary message is sent with:

- Status (success/error/timeout)
- Project path
- File/directory counts
- User who initiated the command

## Testing

### Run Tests

```bash
python -m pytest
```

### Run Tests with Code Coverage

```bash
python -m pytest --cov=src --cov-report=term-missing
```

This displays a coverage summary with line numbers for uncovered code.

### Generate HTML Coverage Report

```bash
python -m pytest --cov=src --cov-report=html
```

The HTML report is saved to `htmlcov/index.html`.

### Additional Coverage Options

```bash
# Fail if coverage drops below threshold (e.g., 80%)
python -m pytest --cov=src --cov-fail-under=80

# Generate multiple report formats
python -m pytest --cov=src --cov-report=term-missing --cov-report=html --cov-report=xml
```


