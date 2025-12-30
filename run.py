"""
Discord Copilot Bot
A Discord bot that executes copilot-cli to create projects based on user prompts.

Entry point for the application.
"""

from src.config import init_config
from src.bot import get_bot, run_bot
from src.commands import setup_createproject_command, setup_session_commands, setup_message_listener
from src.utils.startup_checks import run_startup_checks

# Initialize configuration (load .env, create directories)
init_config()

# Run startup checks to validate all integrations
# This will exit with an error if critical checks fail (Discord token, folder access, Copilot CLI)
run_startup_checks(exit_on_critical=True)

# Get bot instance and set up commands
bot = get_bot()
setup_createproject_command(bot)
setup_session_commands(bot)
setup_message_listener(bot)

if __name__ == "__main__":
    run_bot()

