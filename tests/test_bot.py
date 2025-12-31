"""
Tests for bot module.

This module tests the CopilotBot class, bot configuration, on_ready handler,
run_bot function, and graceful shutdown functionality.
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock

from src.config import DISCORD_BOT_TOKEN, PROJECTS_DIR, MAX_PARALLEL_REQUESTS


class TestBotConfiguration:
    """Tests for bot configuration values."""
    
    def test_config_values(self):
        """
        Tests bot configuration:
        - PROJECTS_DIR is configured with correct name
        - DISCORD_BOT_TOKEN is None or string
        """
        assert PROJECTS_DIR is not None
        assert PROJECTS_DIR.name == "projects"
        assert DISCORD_BOT_TOKEN is None or isinstance(DISCORD_BOT_TOKEN, str)


class TestCopilotBot:
    """Tests for CopilotBot class covering factory functions, singleton pattern, and semaphore."""
    
    def test_bot_factory_functions(self):
        """
        Tests bot factory and singleton patterns:
        - get_bot returns CopilotBot instance with command tree
        - create_bot returns new instances each time
        - get_bot returns same singleton instance
        - reset_bot clears the singleton
        """
        from src.bot import get_bot, create_bot, reset_bot, CopilotBot
        
        # get_bot returns proper instance
        bot = get_bot()
        assert bot is not None
        assert isinstance(bot, CopilotBot)
        assert hasattr(bot, 'tree')
        
        # create_bot returns new instances
        bot1 = create_bot()
        bot2 = create_bot()
        assert isinstance(bot1, CopilotBot)
        assert isinstance(bot2, CopilotBot)
        assert bot1 is not bot2
        
        # get_bot returns singleton
        bot3 = get_bot()
        bot4 = get_bot()
        assert bot3 is bot4
        
        # reset_bot clears singleton
        reset_bot()
        bot5 = get_bot()
        assert bot5 is not None
    
    def test_run_bot_requires_token(self):
        """Tests that run_bot raises ValueError without DISCORD_BOT_TOKEN."""
        from src.bot import run_bot
        
        with patch('src.bot.DISCORD_BOT_TOKEN', None):
            with pytest.raises(ValueError, match="DISCORD_BOT_TOKEN"):
                run_bot()
    
    def test_bot_attributes(self):
        """
        Tests bot internal attributes:
        - Has _shutdown_event (None initially)
        - Has _request_semaphore attribute (None, lazy init)
        """
        from src.bot import create_bot
        bot = create_bot()
        
        assert hasattr(bot, '_shutdown_event')
        assert bot._shutdown_event is None
        
        assert hasattr(bot, '_request_semaphore')
        assert bot._request_semaphore is None
    
    @pytest.mark.asyncio
    async def test_request_semaphore(self):
        """
        Tests request_semaphore property:
        - Returns asyncio.Semaphore instance
        - Returns same instance (singleton per bot)
        - Correctly limits concurrency
        """
        import asyncio
        from src.bot import create_bot, MAX_PARALLEL_REQUESTS
        
        bot = create_bot()
        
        # Returns Semaphore
        semaphore = bot.request_semaphore
        assert isinstance(semaphore, asyncio.Semaphore)
        
        # Same instance on repeated access
        semaphore2 = bot.request_semaphore
        assert semaphore is semaphore2
        
        # Limits concurrency
        concurrent_count = 0
        max_concurrent = 0
        
        async def mock_operation():
            nonlocal concurrent_count, max_concurrent
            await semaphore.acquire()
            try:
                concurrent_count += 1
                max_concurrent = max(max_concurrent, concurrent_count)
                await asyncio.sleep(0.05)
            finally:
                concurrent_count -= 1
                semaphore.release()
        
        tasks = [asyncio.create_task(mock_operation()) for _ in range(MAX_PARALLEL_REQUESTS + 2)]
        await asyncio.gather(*tasks)
        assert max_concurrent <= MAX_PARALLEL_REQUESTS


class TestOnReadyHandler:
    """Tests for on_ready handler covering logging and GitHub status display."""
    
    @pytest.mark.asyncio
    async def test_on_ready_logging(self):
        """
        Tests on_ready_handler logging:
        - Logs info when bot is ready
        - Logs GitHub status (enabled+configured, enabled+not configured, disabled)
        """
        from src.bot import on_ready_handler, CopilotBot
        
        mock_bot = MagicMock(spec=CopilotBot)
        mock_bot.user = MagicMock()
        mock_bot.user.id = 12345
        mock_bot.user.__str__ = MagicMock(return_value="TestBot#1234")
        
        # Test basic logging
        with patch('src.bot.logger') as mock_logger:
            with patch('src.bot.PROJECTS_DIR') as mock_dir:
                mock_dir.absolute.return_value = "/projects"
                await on_ready_handler(mock_bot)
                assert mock_logger.info.called
        
        # Test GitHub enabled and configured
        with patch('src.bot.logger') as mock_logger:
            with patch('src.bot.PROJECTS_DIR') as mock_dir:
                mock_dir.absolute.return_value = "/projects"
                with patch('src.bot.GITHUB_ENABLED', True):
                    with patch('src.bot.GITHUB_TOKEN', 'valid_token'):
                        with patch('src.bot.GITHUB_USERNAME', 'testuser'):
                            await on_ready_handler(mock_bot)
                            assert mock_logger.info.called
        
        # Test GitHub enabled but not configured
        with patch('src.bot.logger') as mock_logger:
            with patch('src.bot.PROJECTS_DIR') as mock_dir:
                mock_dir.absolute.return_value = "/projects"
                with patch('src.bot.GITHUB_ENABLED', True):
                    with patch('src.bot.GITHUB_TOKEN', None):
                        with patch('src.bot.GITHUB_USERNAME', None):
                            await on_ready_handler(mock_bot)
                            assert mock_logger.info.called
        
        # Test GitHub disabled
        with patch('src.bot.logger') as mock_logger:
            with patch('src.bot.PROJECTS_DIR') as mock_dir:
                mock_dir.absolute.return_value = "/projects"
                with patch('src.bot.GITHUB_ENABLED', False):
                    await on_ready_handler(mock_bot)
                    assert mock_logger.info.called
    
    @pytest.mark.asyncio
    async def test_on_ready_warnings(self):
        """
        Tests on_ready warnings for missing configuration:
        - Warns when GitHub enabled but token missing
        - Warns when GitHub enabled but username missing
        """
        from src.bot import on_ready_handler, CopilotBot
        
        mock_bot = MagicMock(spec=CopilotBot)
        mock_bot.user = MagicMock()
        mock_bot.user.id = 12345
        
        # Missing token
        with patch('src.bot.logger') as mock_logger:
            with patch('src.bot.PROJECTS_DIR') as mock_dir:
                mock_dir.absolute.return_value = "/projects"
                with patch('src.bot.GITHUB_ENABLED', True):
                    with patch('src.bot.GITHUB_TOKEN', None):
                        with patch('src.bot.GITHUB_USERNAME', 'test_user'):
                            await on_ready_handler(mock_bot)
                            assert mock_logger.warning.called
        
        # Missing username
        with patch('src.bot.logger') as mock_logger:
            with patch('src.bot.PROJECTS_DIR') as mock_dir:
                mock_dir.absolute.return_value = "/projects"
                with patch('src.bot.GITHUB_ENABLED', True):
                    with patch('src.bot.GITHUB_TOKEN', 'test_token'):
                        with patch('src.bot.GITHUB_USERNAME', None):
                            await on_ready_handler(mock_bot)
                            assert mock_logger.warning.called
    
    @pytest.mark.asyncio
    async def test_setup_hook(self):
        """Tests that setup_hook syncs the command tree."""
        from src.bot import create_bot
        
        bot = create_bot()
        bot.tree.sync = AsyncMock()
        
        await bot.setup_hook()
        
        bot.tree.sync.assert_called_once()


class TestRunBot:
    """Tests for run_bot function covering token validation and bot.run call."""
    
    def test_run_bot_with_token(self):
        """Tests run_bot calls bot.run with DISCORD_BOT_TOKEN."""
        from src.bot import run_bot, reset_bot
        
        reset_bot()  # Start fresh
        
        with patch('src.bot.DISCORD_BOT_TOKEN', 'test_token'):
            with patch('src.bot.get_bot') as mock_get_bot:
                mock_bot = MagicMock()
                mock_get_bot.return_value = mock_bot
                
                with patch('src.bot.setup_signal_handlers'):
                    run_bot()
                    
                    mock_bot.run.assert_called_once_with('test_token')


class TestGracefulShutdown:
    """Tests for graceful shutdown functionality including signal handling."""
    
    def test_signal_handler_setup_and_execution(self):
        """
        Tests signal handler setup and execution:
        - Signal handlers can be set up without error
        - SIGINT handler is registered (not default)
        - Handler kills all processes and exits
        - Handler schedules cleanup when event loop is running
        """
        from src.bot import setup_signal_handlers, create_bot
        import signal
        
        bot = create_bot()
        
        # Signal handlers can be set up
        setup_signal_handlers(bot)
        
        # SIGINT handler is registered
        handler = signal.getsignal(signal.SIGINT)
        assert handler is not signal.SIG_DFL
        
        # Handler kills processes and exits when loop not running
        with patch('src.bot.get_process_registry') as mock_get_registry:
            mock_registry = MagicMock()
            mock_get_registry.return_value = mock_registry
            
            with patch('src.bot.asyncio.get_event_loop') as mock_get_loop:
                mock_loop = MagicMock()
                mock_loop.is_running.return_value = False
                mock_get_loop.return_value = mock_loop
                
                with patch('src.bot.sys.exit') as mock_exit:
                    handler(signal.SIGINT, None)
                    
                    mock_get_registry.assert_called_once()
                    mock_registry.kill_all_sync.assert_called_once()
                    mock_exit.assert_called_once_with(0)
        
        # Handler schedules cleanup when loop is running
        bot2 = create_bot()
        bot2.cleanup = AsyncMock()
        setup_signal_handlers(bot2)
        handler2 = signal.getsignal(signal.SIGINT)
        
        with patch('src.bot.get_process_registry') as mock_get_registry:
            mock_registry = MagicMock()
            mock_get_registry.return_value = mock_registry
            
            with patch('src.bot.asyncio.get_event_loop') as mock_get_loop:
                mock_loop = MagicMock()
                mock_loop.is_running.return_value = True
                mock_get_loop.return_value = mock_loop
                
                with patch('src.bot.asyncio.create_task') as mock_create_task:
                    with patch('src.bot.sys.exit') as mock_exit:
                        handler(signal.SIGINT, None)
                        
                        mock_create_task.assert_called_once()
                        mock_exit.assert_called_once_with(0)
    
    @pytest.mark.asyncio
    async def test_bot_cleanup(self):
        """
        Tests bot cleanup method:
        - Can be called when not closed (calls close)
        - Handles already-closed state (skips close)
        """
        from src.bot import create_bot
        
        # When not closed - calls close
        bot = create_bot()
        bot.close = AsyncMock()
        bot.is_closed = MagicMock(return_value=False)
        
        await bot.cleanup()
        bot.close.assert_called_once()
        
        # When already closed - skips close
        bot2 = create_bot()
        bot2.close = AsyncMock()
        bot2.is_closed = MagicMock(return_value=True)
        
        await bot2.cleanup()
        bot2.close.assert_not_called()
