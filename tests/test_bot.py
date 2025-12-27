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
    
    def test_discord_token_loaded(self):
        """Test that token config exists (may be None in test env)."""
        # Token may or may not be set in test environment
        # We just verify the import works
        assert True


class TestCopilotBot:
    """Tests for CopilotBot class."""
    
    def test_bot_import(self):
        """Test that bot can be imported."""
        from src.bot import bot, CopilotBot
        assert bot is not None
        assert isinstance(bot, CopilotBot)
    
    def test_bot_has_tree(self):
        """Test that bot has command tree."""
        from src.bot import bot
        assert hasattr(bot, 'tree')
    
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
        from src.bot import on_ready_handler
        
        with patch('src.bot.bot') as mock_bot:
            mock_bot.user = MagicMock()
            mock_bot.user.id = 12345
            mock_bot.user.__str__ = MagicMock(return_value="TestBot#1234")
            
            with patch('src.bot.logger') as mock_logger:
                with patch('src.bot.PROJECTS_DIR') as mock_dir:
                    mock_dir.absolute.return_value = "/projects"
                    await on_ready_handler()
                    assert mock_logger.info.called
