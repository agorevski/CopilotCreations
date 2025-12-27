# Discord Copilot Bot - Usage Guide

## Setup

### Prerequisites

- Python 3.10+
- Discord bot token
- `copilot-cli` installed and configured

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/agorevski/CopilotCreations.git
   cd CopilotCreations
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Configure environment:
   ```bash
   cp .env.example .env
   # Edit .env and add your DISCORD_BOT_TOKEN
   ```

4. Run the bot:
   ```bash
   python run.py
   ```

## Discord Commands

### `/createproject`

Creates a new project using Copilot CLI.

**Parameters:**
- `prompt` (required): The prompt describing what project to create
- `model` (optional): The AI model to use (e.g., `gpt-4`, `claude-3-opus`)

**Example:**
```
/createproject prompt:"Create a Python Flask REST API with user authentication"
/createproject prompt:"Build a React todo app" model:gpt-4
```

**Output:**
1. **Project Location** - Shows the folder structure in real-time
2. **Copilot Output** - Shows the CLI output in real-time
3. **Project Summary** - Final summary with log file attachment

## Configuration

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `DISCORD_BOT_TOKEN` | Discord bot token | Yes |

### `.folderignore`

Control which folders are collapsed in the folder tree display:

```gitignore
# Dependencies
node_modules/
venv/

# Build outputs
dist/
build/

# IDE
.vscode/
.idea/
```

Ignored folders appear as: `node_modules/ (1234 files)`

## Running Tests

```bash
# Install test dependencies
pip install pytest pytest-cov

# Run all tests
pytest tests/

# Run with verbose output
pytest tests/ -v

# Run with coverage report
pytest tests/ --cov=src --cov-report=term-missing

# Generate HTML coverage report
pytest tests/ --cov=src --cov-report=html
# Open htmlcov/index.html in browser
```

### Coverage Requirements

The project requires **>75% test coverage**. Current coverage: **78%+**

Coverage configuration is in `pyproject.toml`.

## Project Output

Projects are created in the `projects/` directory with the naming format:
```
{username}_{timestamp}_{unique_id}/
```

Example: `john_doe_20231227_143052_a1b2c3d4/`

## Log Files

Each project creation generates a markdown log file containing:
- Session ID
- Start time and duration
- Status (success/error/timeout)
- Model used
- File and directory counts
- Full prompt
- Complete execution log

## Troubleshooting

### Bot not responding to commands

1. Ensure the bot has proper permissions
2. Check that slash commands are synced (restart bot)
3. Verify the bot token is correct

### Timeout errors

Projects have a 30-minute timeout. For larger projects:
- Break into smaller prompts
- Use a faster model

### Permission errors

Ensure the bot has:
- Send Messages
- Attach Files
- Use Application Commands
