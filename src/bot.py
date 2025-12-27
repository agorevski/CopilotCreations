"""
Discord bot client for the Copilot Bot.
"""

import discord
from discord import app_commands

from .config import DISCORD_BOT_TOKEN, PROJECTS_DIR
from .utils.logging import logger


class CopilotBot(discord.Client):
    """Discord bot client with application commands support."""
    
    def __init__(self):
        intents = discord.Intents.default()
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        """Called when the bot is ready to set up commands."""
        await self.tree.sync()


# Global bot instance
bot = CopilotBot()


async def on_ready_handler():
    """Handle the on_ready event."""
    logger.info(f"Bot is ready! Logged in as {bot.user}")
    logger.info(f"Projects will be saved to: {PROJECTS_DIR.absolute()}")
    logger.info(
        f"Invite URL: https://discord.com/api/oauth2/authorize?"
        f"client_id={bot.user.id}&permissions=274877975552&scope=bot%20applications.commands"
    )


@bot.event
async def on_ready():
    """Discord event handler for when the bot is ready."""
    await on_ready_handler()


def run_bot():
    """Start the Discord bot."""
    if not DISCORD_BOT_TOKEN:
        raise ValueError("DISCORD_BOT_TOKEN environment variable is required")
    
    logger.info("Starting Discord Copilot Bot...")
    bot.run(DISCORD_BOT_TOKEN)
