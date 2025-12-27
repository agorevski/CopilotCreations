"""
Discord bot client for the Copilot Bot.
"""

import asyncio
import signal
import sys
from typing import Optional

import discord
from discord import app_commands

from .config import DISCORD_BOT_TOKEN, PROJECTS_DIR, GITHUB_ENABLED, GITHUB_TOKEN, GITHUB_USERNAME
from .utils.logging import logger


class CopilotBot(discord.Client):
    """Discord bot client with application commands support."""
    
    def __init__(self) -> None:
        intents = discord.Intents.default()
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)
        self._shutdown_event: Optional[asyncio.Event] = None

    async def setup_hook(self) -> None:
        """Called when the bot is ready to set up commands."""
        await self.tree.sync()
    
    async def cleanup(self) -> None:
        """Cleanup resources before shutdown."""
        logger.info("Cleaning up resources...")
        # Close the Discord connection gracefully
        if not self.is_closed():
            await self.close()
        logger.info("Cleanup complete")


# Bot instance management using factory pattern
_bot_instance: Optional[CopilotBot] = None


def get_bot() -> CopilotBot:
    """Get or create the bot instance (singleton pattern)."""
    global _bot_instance
    if _bot_instance is None:
        _bot_instance = CopilotBot()
    return _bot_instance


def create_bot() -> CopilotBot:
    """Create a new bot instance (useful for testing)."""
    return CopilotBot()


def reset_bot() -> None:
    """Reset the global bot instance (useful for testing)."""
    global _bot_instance
    _bot_instance = None


async def on_ready_handler(bot: CopilotBot) -> None:
    """Handle the on_ready event."""
    logger.info(f"Bot is ready! Logged in as {bot.user}")
    logger.info(f"Projects will be saved to: {PROJECTS_DIR.absolute()}")
    
    # Log GitHub configuration status
    if GITHUB_ENABLED:
        if GITHUB_TOKEN and GITHUB_USERNAME:
            logger.info(f"GitHub integration: ENABLED (user: {GITHUB_USERNAME})")
        else:
            missing = []
            if not GITHUB_TOKEN:
                missing.append("GITHUB_TOKEN")
            if not GITHUB_USERNAME:
                missing.append("GITHUB_USERNAME")
            logger.warning(f"GitHub integration: ENABLED but missing: {', '.join(missing)}")
    else:
        logger.info("GitHub integration: DISABLED (set GITHUB_ENABLED=true in .env to enable)")
    
    logger.info(
        f"Invite URL: https://discord.com/api/oauth2/authorize?"
        f"client_id={bot.user.id}&permissions=274877975552&scope=bot%20applications.commands"
    )


def setup_signal_handlers(bot: CopilotBot) -> None:
    """Set up signal handlers for graceful shutdown."""
    def signal_handler(sig: int, frame) -> None:
        logger.info(f"Received signal {sig}, initiating graceful shutdown...")
        # Schedule cleanup in the event loop
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.create_task(bot.cleanup())
        sys.exit(0)
    
    # Register signal handlers (SIGTERM may not exist on Windows)
    signal.signal(signal.SIGINT, signal_handler)
    if hasattr(signal, 'SIGTERM'):
        signal.signal(signal.SIGTERM, signal_handler)


def run_bot() -> None:
    """Start the Discord bot."""
    if not DISCORD_BOT_TOKEN:
        raise ValueError("DISCORD_BOT_TOKEN environment variable is required")
    
    bot = get_bot()
    
    # Set up event handlers
    @bot.event
    async def on_ready() -> None:
        """Discord event handler for when the bot is ready."""
        await on_ready_handler(bot)
    
    # Set up signal handlers for graceful shutdown
    setup_signal_handlers(bot)
    
    logger.info("Starting Discord Copilot Bot...")
    bot.run(DISCORD_BOT_TOKEN)


# For backward compatibility, expose bot as a property
# that uses the factory function
@property
def bot() -> CopilotBot:
    """Get the bot instance."""
    return get_bot()


# Re-export for backward compatibility
bot = get_bot()
