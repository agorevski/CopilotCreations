"""
Discord Copilot Bot
A Discord bot that executes copilot-cli to create projects based on user prompts.

Entry point for the application.
"""

from src.bot import bot, run_bot
from src.commands import setup_createproject_command

# Set up commands
setup_createproject_command(bot)

if __name__ == "__main__":
    run_bot()

