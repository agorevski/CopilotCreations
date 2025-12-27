# Discord Copilot Bot

A Discord bot that executes `copilot-cli` to create projects based on user prompts, with real-time progress updates and optional GitHub integration.

## Features

- `/createproject` slash command to generate projects from natural language prompts
- Real-time file tree and output updates in Discord
- 30-minute timeout protection with concurrent user support
- Session logging with markdown log file attachments
- **GitHub Integration** - Automatically create repositories and push project files
- **Graceful Shutdown** - Proper signal handling for clean process termination
- **Thread-Safe Operations** - Async-safe output buffering prevents race conditions

## Quick Start

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Configure your Discord bot token:
   ```bash
   cp .env.example .env
   # Edit .env and add your DISCORD_BOT_TOKEN
   ```

3. (Optional) Configure GitHub integration:
   ```bash
   # Edit .env and set:
   # GITHUB_ENABLED=true
   # GITHUB_TOKEN=your_github_personal_access_token
   # GITHUB_USERNAME=your_github_username
   ```

4. Run the bot:
   ```bash
   python run.py
   ```

## GitHub Integration

When enabled, the bot automatically:
- Creates a new private GitHub repository for each project
- Copies the root `.gitignore` to ensure clean repositories
- Pushes all generated files to the repository
- Provides a direct link to the repository in the Discord summary

To set up GitHub integration:
1. Create a Personal Access Token at https://github.com/settings/tokens
2. Required scopes: `repo` (Full control of private repositories)
3. Add credentials to your `.env` file

## Architecture Highlights

- **Factory Pattern** - Bot instances are created via `get_bot()` factory function for better testability
- **Explicit Initialization** - Configuration is loaded via `init_config()` at startup, not at import time
- **Modular Design** - Long command handlers are broken into focused helper functions
- **Thread-Safe Buffers** - `AsyncOutputBuffer` class provides race-condition-free concurrent access

## Documentation

- **[Usage Guide](docs/USAGE.md)** - Detailed setup, commands, configuration, and troubleshooting
- **[Architecture](docs/ARCHITECTURE.md)** - Project structure, components, and data flow

## Testing

```bash
python -m pytest                                    # Run tests
python -m pytest --cov=src --cov-report=term-missing  # With coverage
```

See [Usage Guide](docs/USAGE.md#running-tests) for more testing options.
