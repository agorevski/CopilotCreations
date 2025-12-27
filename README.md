# Discord Copilot Bot

A Discord bot that executes `copilot-cli` to create projects based on user prompts.

## Features

- `/createproject prompt:<prompt> [model:<model>]` - Create a new project using Copilot CLI
- Real-time file tree updates (every 5 seconds)
- Rolling output window showing last 2000 characters (every 3 seconds)
- 30-minute timeout protection
- Concurrent user support
- Full error handling with stack traces

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
