"""
Discord bot client for the Copilot Bot.
"""

import asyncio
import signal
import sys
from typing import Optional

import discord
from discord import app_commands

from .config import DISCORD_BOT_TOKEN, PROJECTS_DIR, GITHUB_ENABLED, GITHUB_TOKEN, GITHUB_USERNAME, MAX_PARALLEL_REQUESTS
from .utils.logging import logger
from .utils.process_registry import get_process_registry


class CopilotBot(discord.Client):
    """Discord bot client with application commands support."""
    
    def __init__(self) -> None:
        """
        Initialize the CopilotBot with required intents and command tree.
        
        Sets up Discord intents for message content access and initializes
        the application command tree for slash commands.
        """
        intents = discord.Intents.default()
        intents.message_content = True  # Required for reading message content in sessions
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)
        self._shutdown_event: Optional[asyncio.Event] = None
        self._request_semaphore: Optional[asyncio.Semaphore] = None

    @property
    def request_semaphore(self) -> asyncio.Semaphore:
        """
        Get or create the request semaphore for limiting parallel requests.
        
        Returns:
            asyncio.Semaphore: A semaphore initialized with MAX_PARALLEL_REQUESTS
            to control concurrent request handling.
        """
        if self._request_semaphore is None:
            self._request_semaphore = asyncio.Semaphore(MAX_PARALLEL_REQUESTS)
        return self._request_semaphore

    async def setup_hook(self) -> None:
        """
        Called when the bot is ready to set up commands.
        
        Synchronizes the application command tree with Discord to register
        all slash commands globally.
        """
        await self.tree.sync()
    
    async def cleanup(self) -> None:
        """
        Cleanup resources before shutdown.
        
        Gracefully closes the Discord connection if still open and logs
        the cleanup process. Should be called during shutdown sequence.
        """
        logger.info("Cleaning up resources...")
        # Close the Discord connection gracefully
        if not self.is_closed():
            await self.close()
        logger.info("Cleanup complete")


# Bot instance management using factory pattern
_bot_instance: Optional[CopilotBot] = None


def get_bot() -> CopilotBot:
    """
    Get or create the bot instance using singleton pattern.
    
    Returns:
        CopilotBot: The global bot instance. Creates a new instance if none exists.
    """
    global _bot_instance
    if _bot_instance is None:
        _bot_instance = CopilotBot()
    return _bot_instance


def create_bot() -> CopilotBot:
    """
    Create a new bot instance independent of the global singleton.
    
    Returns:
        CopilotBot: A fresh bot instance. Useful for testing scenarios
        where isolated instances are needed.
    """
    return CopilotBot()


def reset_bot() -> None:
    """
    Reset the global bot instance to None.
    
    Clears the singleton instance, allowing a fresh bot to be created
    on the next get_bot() call. Primarily used in testing for cleanup.
    """
    global _bot_instance
    _bot_instance = None


async def on_ready_handler(bot: CopilotBot) -> None:
    """
    Handle the on_ready event when the bot successfully connects to Discord.
    
    Args:
        bot: The CopilotBot instance that triggered the ready event.
        
    Logs bot status, configuration details including GitHub integration status,
    and generates the OAuth2 invite URL for adding the bot to servers.
    """
    logger.info(f"Bot is ready! Logged in as {bot.user}")
    logger.info(f"Projects will be saved to: {PROJECTS_DIR.absolute()}")
    logger.info(f"Max parallel requests: {MAX_PARALLEL_REQUESTS}")
    
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
    """
    Set up signal handlers for graceful shutdown.
    
    Args:
        bot: The CopilotBot instance to clean up on shutdown.
        
    Registers handlers for SIGINT and SIGTERM (where available) to ensure
    subprocesses are killed and resources are cleaned up before exit.
    """
    def signal_handler(sig: int, frame) -> None:
        logger.info(f"Received signal {sig}, initiating graceful shutdown...")
        # Kill all tracked subprocesses synchronously
        process_registry = get_process_registry()
        process_registry.kill_all_sync()
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
    """
    Start the Discord bot and begin handling events.
    
    Raises:
        ValueError: If DISCORD_BOT_TOKEN environment variable is not set.
        
    Initializes the bot, sets up event handlers and signal handlers,
    then starts the blocking run loop to process Discord events.
    """
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
    """
    Get the bot instance for backward compatibility.
    
    Returns:
        CopilotBot: The global bot instance via get_bot().
    """
    return get_bot()


# Re-export for backward compatibility
bot = get_bot()
