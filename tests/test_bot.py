"""
Tests for bot module.
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock

from src.config import DISCORD_BOT_TOKEN, PROJECTS_DIR


class TestBotConfiguration:
    """Tests for bot configuration."""
    
    def test_projects_dir_exists(self):
        """Test that projects directory is configured."""
        assert PROJECTS_DIR is not None
        assert PROJECTS_DIR.name == "projects"
    
    def test_discord_token_config_accessible(self):
        """Test that DISCORD_BOT_TOKEN config is accessible."""
        # Verify the config value is either None or a string
        assert DISCORD_BOT_TOKEN is None or isinstance(DISCORD_BOT_TOKEN, str)


class TestCopilotBot:
    """Tests for CopilotBot class."""
    
    def test_bot_import(self):
        """Test that bot can be imported via factory function."""
        from src.bot import get_bot, CopilotBot
        bot = get_bot()
        assert bot is not None
        assert isinstance(bot, CopilotBot)
    
    def test_bot_has_tree(self):
        """Test that bot has command tree."""
        from src.bot import get_bot
        bot = get_bot()
        assert hasattr(bot, 'tree')
    
    def test_create_bot_returns_new_instance(self):
        """Test that create_bot returns a new instance."""
        from src.bot import create_bot, CopilotBot
        bot1 = create_bot()
        bot2 = create_bot()
        assert isinstance(bot1, CopilotBot)
        assert isinstance(bot2, CopilotBot)
        assert bot1 is not bot2
    
    def test_get_bot_returns_same_instance(self):
        """Test that get_bot returns the same singleton instance."""
        from src.bot import get_bot
        bot1 = get_bot()
        bot2 = get_bot()
        assert bot1 is bot2
    
    def test_run_bot_requires_token(self):
        """Test that run_bot raises error without token."""
        from src.bot import run_bot
        
        with patch('src.bot.DISCORD_BOT_TOKEN', None):
            with pytest.raises(ValueError, match="DISCORD_BOT_TOKEN"):
                run_bot()


class TestOnReadyHandler:
    """Tests for on_ready handler."""
    
    @pytest.mark.asyncio
    async def test_on_ready_handler_logs(self):
        """Test on_ready_handler calls logger."""
        from src.bot import on_ready_handler, CopilotBot
        
        with patch.object(CopilotBot, 'user', new_callable=lambda: property(lambda self: MagicMock(id=12345))):
            mock_bot = MagicMock(spec=CopilotBot)
            mock_bot.user = MagicMock()
            mock_bot.user.id = 12345
            mock_bot.user.__str__ = MagicMock(return_value="TestBot#1234")
            
            with patch('src.bot.logger') as mock_logger:
                with patch('src.bot.PROJECTS_DIR') as mock_dir:
                    mock_dir.absolute.return_value = "/projects"
                    await on_ready_handler(mock_bot)
                    assert mock_logger.info.called


class TestGracefulShutdown:
    """Tests for graceful shutdown functionality."""
    
    def test_setup_signal_handlers(self):
        """Test that signal handlers can be set up."""
        from src.bot import setup_signal_handlers, create_bot
        import signal
        
        bot = create_bot()
        # Should not raise any exceptions
        setup_signal_handlers(bot)
        
        # Verify SIGINT handler is set (it won't be the default)
        handler = signal.getsignal(signal.SIGINT)
        assert handler is not signal.SIG_DFL
    
    @pytest.mark.asyncio
    async def test_bot_cleanup(self):
        """Test that bot cleanup method can be called."""
        from src.bot import create_bot
        
        bot = create_bot()
        # Mock the close method since we're not connected
        bot.close = AsyncMock()
        bot.is_closed = MagicMock(return_value=False)
        
        await bot.cleanup()
        
        bot.close.assert_called_once()
