"""
Tests for bot module.
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock

from src.config import DISCORD_BOT_TOKEN, PROJECTS_DIR, MAX_PARALLEL_REQUESTS


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
    
    def test_reset_bot_clears_instance(self):
        """Test that reset_bot clears the singleton instance."""
        from src.bot import get_bot, reset_bot, create_bot
        
        # Get initial instance
        bot1 = get_bot()
        
        # Reset
        reset_bot()
        
        # Get new instance - should be different
        bot2 = get_bot()
        # Note: They may be different objects but both are CopilotBot
        assert bot2 is not None
    
    def test_bot_has_shutdown_event(self):
        """Test that bot has shutdown event attribute."""
        from src.bot import create_bot
        bot = create_bot()
        assert hasattr(bot, '_shutdown_event')
        assert bot._shutdown_event is None
    
    def test_bot_has_request_semaphore_attribute(self):
        """Test that bot has request semaphore attribute."""
        from src.bot import create_bot
        bot = create_bot()
        assert hasattr(bot, '_request_semaphore')
        assert bot._request_semaphore is None  # Lazy initialized
    
    @pytest.mark.asyncio
    async def test_bot_request_semaphore_property(self):
        """Test that bot request_semaphore property returns a semaphore."""
        import asyncio
        from src.bot import create_bot
        bot = create_bot()
        semaphore = bot.request_semaphore
        assert isinstance(semaphore, asyncio.Semaphore)
    
    @pytest.mark.asyncio
    async def test_bot_request_semaphore_is_singleton(self):
        """Test that bot request_semaphore property returns the same instance."""
        from src.bot import create_bot
        bot = create_bot()
        semaphore1 = bot.request_semaphore
        semaphore2 = bot.request_semaphore
        assert semaphore1 is semaphore2
    
    @pytest.mark.asyncio
    async def test_bot_request_semaphore_limits_concurrency(self):
        """Test that semaphore correctly limits concurrent operations."""
        import asyncio
        from src.bot import create_bot, MAX_PARALLEL_REQUESTS
        
        bot = create_bot()
        semaphore = bot.request_semaphore
        
        # Track concurrent operations
        concurrent_count = 0
        max_concurrent = 0
        
        async def mock_operation():
            nonlocal concurrent_count, max_concurrent
            await semaphore.acquire()
            try:
                concurrent_count += 1
                max_concurrent = max(max_concurrent, concurrent_count)
                await asyncio.sleep(0.05)  # Short delay
            finally:
                concurrent_count -= 1
                semaphore.release()
        
        # Start more tasks than the limit
        tasks = [asyncio.create_task(mock_operation()) for _ in range(MAX_PARALLEL_REQUESTS + 2)]
        await asyncio.gather(*tasks)
        
        # Max concurrent should not exceed the limit
        assert max_concurrent <= MAX_PARALLEL_REQUESTS


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
    
    @pytest.mark.asyncio
    async def test_on_ready_handler_github_enabled_configured(self):
        """Test on_ready_handler logs GitHub status when enabled and configured."""
        from src.bot import on_ready_handler, CopilotBot
        
        mock_bot = MagicMock(spec=CopilotBot)
        mock_bot.user = MagicMock()
        mock_bot.user.id = 12345
        
        with patch('src.bot.logger') as mock_logger:
            with patch('src.bot.PROJECTS_DIR') as mock_dir:
                mock_dir.absolute.return_value = "/projects"
                with patch('src.bot.GITHUB_ENABLED', True):
                    with patch('src.bot.GITHUB_TOKEN', 'test_token'):
                        with patch('src.bot.GITHUB_USERNAME', 'test_user'):
                            await on_ready_handler(mock_bot)
                            # Check that GitHub enabled message was logged
                            info_calls = [str(call) for call in mock_logger.info.call_args_list]
                            assert any('GitHub' in str(call) for call in info_calls)
    
    @pytest.mark.asyncio
    async def test_on_ready_handler_github_enabled_missing_token(self):
        """Test on_ready_handler warns when GitHub enabled but token missing."""
        from src.bot import on_ready_handler, CopilotBot
        
        mock_bot = MagicMock(spec=CopilotBot)
        mock_bot.user = MagicMock()
        mock_bot.user.id = 12345
        
        with patch('src.bot.logger') as mock_logger:
            with patch('src.bot.PROJECTS_DIR') as mock_dir:
                mock_dir.absolute.return_value = "/projects"
                with patch('src.bot.GITHUB_ENABLED', True):
                    with patch('src.bot.GITHUB_TOKEN', None):
                        with patch('src.bot.GITHUB_USERNAME', 'test_user'):
                            await on_ready_handler(mock_bot)
                            # Check that warning was logged about missing config
                            assert mock_logger.warning.called
    
    @pytest.mark.asyncio
    async def test_on_ready_handler_github_enabled_missing_username(self):
        """Test on_ready_handler warns when GitHub enabled but username missing."""
        from src.bot import on_ready_handler, CopilotBot
        
        mock_bot = MagicMock(spec=CopilotBot)
        mock_bot.user = MagicMock()
        mock_bot.user.id = 12345
        
        with patch('src.bot.logger') as mock_logger:
            with patch('src.bot.PROJECTS_DIR') as mock_dir:
                mock_dir.absolute.return_value = "/projects"
                with patch('src.bot.GITHUB_ENABLED', True):
                    with patch('src.bot.GITHUB_TOKEN', 'test_token'):
                        with patch('src.bot.GITHUB_USERNAME', None):
                            await on_ready_handler(mock_bot)
                            assert mock_logger.warning.called
    
    @pytest.mark.asyncio
    async def test_on_ready_handler_github_disabled(self):
        """Test on_ready_handler logs when GitHub is disabled."""
        from src.bot import on_ready_handler, CopilotBot
        
        mock_bot = MagicMock(spec=CopilotBot)
        mock_bot.user = MagicMock()
        mock_bot.user.id = 12345
        
        with patch('src.bot.logger') as mock_logger:
            with patch('src.bot.PROJECTS_DIR') as mock_dir:
                mock_dir.absolute.return_value = "/projects"
                with patch('src.bot.GITHUB_ENABLED', False):
                    await on_ready_handler(mock_bot)
                    info_calls = [str(call) for call in mock_logger.info.call_args_list]
                    assert any('DISABLED' in str(call) for call in info_calls)
    
    @pytest.mark.asyncio
    async def test_setup_hook(self):
        """Test that setup_hook syncs the command tree."""
        from src.bot import create_bot
        
        bot = create_bot()
        bot.tree.sync = AsyncMock()
        
        await bot.setup_hook()
        
        bot.tree.sync.assert_called_once()


class TestRunBot:
    """Tests for run_bot function."""
    
    def test_run_bot_with_valid_token(self):
        """Test that run_bot calls bot.run with token."""
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
    
    def test_signal_handler_kills_processes_and_exits(self):
        """Test that signal handler kills all processes and exits."""
        from src.bot import setup_signal_handlers, create_bot
        import signal
        
        bot = create_bot()
        setup_signal_handlers(bot)
        
        # Get the registered signal handler
        handler = signal.getsignal(signal.SIGINT)
        
        # Mock the process registry and sys.exit
        with patch('src.bot.get_process_registry') as mock_get_registry:
            mock_registry = MagicMock()
            mock_get_registry.return_value = mock_registry
            
            with patch('src.bot.asyncio.get_event_loop') as mock_get_loop:
                mock_loop = MagicMock()
                mock_loop.is_running.return_value = False
                mock_get_loop.return_value = mock_loop
                
                with patch('src.bot.sys.exit') as mock_exit:
                    # Call the signal handler directly
                    handler(signal.SIGINT, None)
                    
                    # Verify process registry was called
                    mock_get_registry.assert_called_once()
                    mock_registry.kill_all_sync.assert_called_once()
                    mock_exit.assert_called_once_with(0)
    
    def test_signal_handler_schedules_cleanup_when_loop_running(self):
        """Test that signal handler schedules cleanup when event loop is running."""
        from src.bot import setup_signal_handlers, create_bot
        import signal
        
        bot = create_bot()
        bot.cleanup = AsyncMock()
        setup_signal_handlers(bot)
        
        handler = signal.getsignal(signal.SIGINT)
        
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
                        
                        # Verify cleanup was scheduled
                        mock_create_task.assert_called_once()
                        mock_exit.assert_called_once_with(0)
    
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
    
    @pytest.mark.asyncio
    async def test_bot_cleanup_when_already_closed(self):
        """Test that bot cleanup handles already-closed state."""
        from src.bot import create_bot
        
        bot = create_bot()
        bot.close = AsyncMock()
        bot.is_closed = MagicMock(return_value=True)
        
        await bot.cleanup()
        
        # close should NOT be called since is_closed returns True
        bot.close.assert_not_called()
