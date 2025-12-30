"""
Discord Copilot Bot
A Discord bot that executes copilot-cli to create projects based on user prompts.

Entry point for the application.
"""

from src.config import init_config
from src.bot import get_bot, run_bot
from src.commands import setup_createproject_command, setup_session_commands, setup_message_listener

# Initialize configuration (load .env, create directories)
init_config()

# Get bot instance and set up commands
bot = get_bot()
setup_createproject_command(bot)
setup_session_commands(bot)
setup_message_listener(bot)

if __name__ == "__main__":
    run_bot()

