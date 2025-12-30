# Discord Copilot Bot

A Discord bot that executes `copilot-cli` to create projects based on user prompts, with real-time progress updates and optional GitHub integration.

## Features

- `/createproject` slash command to generate projects from natural language prompts
- `/startproject` + `/buildproject` for conversational AI-assisted prompt refinement
- **AI-Powered Prompt Refinement** - Generates exhaustive 12-section project specifications via Azure OpenAI
- **Unified real-time progress** - Single message with folder structure, copilot output, and summary updated every 3 seconds
- **Clean Chat Experience** - Session messages are automatically deleted after project build
- 30-minute timeout protection with concurrent user support
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
   # GITHUB_REPO_PRIVATE=true  # Optional: make repos private
   ```

4. Run the bot:
   ```bash
   python run.py
   ```

## Bot Permissions

The bot requires these Discord permissions:
- **Send Messages** - To send progress updates
- **Read Message History** - To track session messages
- **Attach Files** - To send refined prompt files
- **Use Application Commands** - For slash commands
- **Manage Messages** - To delete session messages after `/buildproject`

To grant permissions, either re-invite the bot with updated OAuth2 scopes or configure the bot's role in Server Settings → Roles.

## GitHub Integration

When enabled, the bot automatically:
- Creates a new GitHub repository for each project (private if `GITHUB_REPO_PRIVATE=true`)
- Copies the root `.gitignore` to ensure clean repositories
- Pushes all generated files to the repository
- Provides a direct link to the repository in the Discord summary
- Optionally deletes local project folder after successful push (`CLEANUP_AFTER_PUSH=true` by default)

To set up GitHub integration:
1. Create a Personal Access Token at https://github.com/settings/tokens
2. Required scopes: `repo` (Full control of private repositories)
3. Add credentials to your `.env` file

## Prompt Configuration

The `config.yaml` file contains prompt templates that are prepended to user prompts for specific commands. This allows customization of the base requirements for project creation (e.g., requiring CI/CD pipelines, documentation, test coverage).

See the file for available configuration options.

## Architecture Highlights

- **Factory Pattern** - Bot instances are created via `get_bot()` factory function for better testability
- **Explicit Initialization** - Directory creation and config loading via `init_config()` at startup
- **Modular Design** - Long command handlers are broken into focused helper functions
- **Thread-Safe Buffers** - `AsyncOutputBuffer` class provides race-condition-free concurrent access
- **Process Registry** - Centralized subprocess tracking for clean termination on shutdown
- **Input Validation** - Prompt length and model name format are validated before processing
- **Consistent Error Formatting** - All error messages use `format_error_message()` for uniform UX
- **Singleton Logger** - Logger uses lazy initialization pattern to avoid import-time side effects

## Documentation

- **[Usage Guide](docs/USAGE.md)** - Detailed setup, commands, configuration, and troubleshooting
- **[Architecture](docs/ARCHITECTURE.md)** - Project structure, components, and data flow

## Testing

```bash
python -m pytest                                    # Run tests
python -m pytest --cov=src --cov-report=term-missing  # With coverage
```

See [Usage Guide](docs/USAGE.md#running-tests) for more testing options.
