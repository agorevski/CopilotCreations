# Discord Copilot Bot

A Discord bot that executes `copilot-cli` to create projects based on user prompts, with real-time progress updates.

## Features

- `/createproject` slash command to generate projects from natural language prompts
- Real-time file tree and output updates in Discord
- 30-minute timeout protection with concurrent user support
- Session logging with markdown log file attachments

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

3. Run the bot:
   ```bash
   python run.py
   ```

## Documentation

- **[Usage Guide](docs/USAGE.md)** - Detailed setup, commands, configuration, and troubleshooting
- **[Architecture](docs/ARCHITECTURE.md)** - Project structure, components, and data flow

## Testing

```bash
python -m pytest                                    # Run tests
python -m pytest --cov=src --cov-report=term-missing  # With coverage
```

See [Usage Guide](docs/USAGE.md#running-tests) for more testing options.
