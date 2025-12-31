"""
Tests for process registry module.

This module tests the ProcessRegistry class which tracks active subprocess
processes for graceful shutdown on signal termination.
"""

import asyncio
import pytest
from unittest.mock import MagicMock, patch, AsyncMock

from src.utils.process_registry import ProcessRegistry, get_process_registry


class TestProcessRegistry:
    """Tests for ProcessRegistry class covering registration, unregistration, and killing."""
    
    def test_initialization(self):
        """
        Tests registry initialization:
        - Empty process set
        - Active count starts at 0
        """
        registry = ProcessRegistry()
        assert registry._processes == set()
        assert registry.active_count == 0
    
    @pytest.mark.asyncio
    async def test_register_and_unregister(self):
        """
        Tests async register/unregister operations:
        - Register single process
        - Register multiple processes
        - Unregister removes from set
        - Unregister non-existent doesn't raise
        - Active count tracks correctly
        """
        registry = ProcessRegistry()
        
        # Register single process
        proc1 = MagicMock()
        proc1.pid = 12345
        await registry.register(proc1)
        assert proc1 in registry._processes
        assert registry.active_count == 1
        
        # Register multiple
        proc2 = MagicMock()
        proc2.pid = 12346
        await registry.register(proc2)
        assert registry.active_count == 2
        assert proc1 in registry._processes
        assert proc2 in registry._processes
        
        # Unregister
        await registry.unregister(proc1)
        assert registry.active_count == 1
        assert proc1 not in registry._processes
        
        # Unregister non-existent (no error)
        proc3 = MagicMock()
        proc3.pid = 99999
        await registry.unregister(proc3)  # Should not raise
        assert registry.active_count == 1
    
    @pytest.mark.asyncio
    async def test_kill_all_async(self):
        """
        Tests async kill_all operations:
        - Empty registry doesn't raise
        - Kills running processes
        - Skips already completed processes
        - Handles timeout during wait
        - Handles exceptions during kill
        - Clears registry after kill
        """
        registry = ProcessRegistry()
        
        # Empty registry
        await registry.kill_all()  # Should not raise
        assert registry.active_count == 0
        
        # Kill running processes
        proc1 = MagicMock()
        proc1.pid = 12345
        proc1.returncode = None  # Running
        proc1.kill = MagicMock()
        proc1.wait = AsyncMock()
        
        proc2 = MagicMock()
        proc2.pid = 12346
        proc2.returncode = None  # Running
        proc2.kill = MagicMock()
        proc2.wait = AsyncMock()
        
        await registry.register(proc1)
        await registry.register(proc2)
        await registry.kill_all()
        
        proc1.kill.assert_called_once()
        proc2.kill.assert_called_once()
        assert registry.active_count == 0
        
        # Skip completed processes
        registry2 = ProcessRegistry()
        completed = MagicMock()
        completed.pid = 111
        completed.returncode = 0  # Already completed
        completed.kill = MagicMock()
        completed.wait = AsyncMock()
        
        await registry2.register(completed)
        await registry2.kill_all()
        completed.kill.assert_not_called()
        
        # Handle timeout
        registry3 = ProcessRegistry()
        timeout_proc = MagicMock()
        timeout_proc.pid = 222
        timeout_proc.returncode = None
        timeout_proc.kill = MagicMock()
        timeout_proc.wait = AsyncMock(side_effect=asyncio.TimeoutError())
        
        await registry3.register(timeout_proc)
        await registry3.kill_all()  # Should not raise
        timeout_proc.kill.assert_called_once()
        
        # Handle exception during kill
        registry4 = ProcessRegistry()
        error_proc = MagicMock()
        error_proc.pid = 333
        error_proc.returncode = None
        error_proc.kill = MagicMock(side_effect=Exception("Kill failed"))
        error_proc.wait = AsyncMock()
        
        await registry4.register(error_proc)
        await registry4.kill_all()  # Should not raise
        assert registry4.active_count == 0
    
    def test_kill_all_sync(self):
        """
        Tests sync kill_all_sync operations:
        - Empty registry doesn't raise
        - Kills running processes
        - Skips completed processes
        - Handles exceptions
        """
        registry = ProcessRegistry()
        
        # Empty registry
        registry.kill_all_sync()
        assert registry.active_count == 0
        
        # Kill running
        proc1 = MagicMock()
        proc1.pid = 12345
        proc1.returncode = None
        proc1.kill = MagicMock()
        
        proc2 = MagicMock()
        proc2.pid = 12346
        proc2.returncode = None
        proc2.kill = MagicMock()
        
        registry._processes.add(proc1)
        registry._processes.add(proc2)
        registry.kill_all_sync()
        
        proc1.kill.assert_called_once()
        proc2.kill.assert_called_once()
        assert registry.active_count == 0
        
        # Skip completed
        registry2 = ProcessRegistry()
        completed = MagicMock()
        completed.pid = 111
        completed.returncode = 0
        completed.kill = MagicMock()
        registry2._processes.add(completed)
        registry2.kill_all_sync()
        completed.kill.assert_not_called()
        
        # Handle exception
        registry3 = ProcessRegistry()
        error_proc = MagicMock()
        error_proc.pid = 222
        error_proc.returncode = None
        error_proc.kill = MagicMock(side_effect=Exception("Kill failed"))
        registry3._processes.add(error_proc)
        registry3.kill_all_sync()  # Should not raise
        assert registry3.active_count == 0
    
    def test_active_count_property(self):
        """Tests active_count property tracks process count correctly."""
        registry = ProcessRegistry()
        
        p1, p2, p3 = MagicMock(), MagicMock(), MagicMock()
        
        registry._processes.add(p1)
        assert registry.active_count == 1
        
        registry._processes.add(p2)
        assert registry.active_count == 2
        
        registry._processes.add(p3)
        assert registry.active_count == 3
        
        registry._processes.discard(p2)
        assert registry.active_count == 2


class TestGetProcessRegistry:
    """Tests for get_process_registry singleton function."""
    
    def test_singleton_behavior(self):
        """
        Tests singleton behavior:
        - Returns ProcessRegistry instance
        - Returns same instance on repeated calls
        """
        import src.utils.process_registry as pr_module
        pr_module._process_registry = None  # Reset
        
        registry1 = get_process_registry()
        assert isinstance(registry1, ProcessRegistry)
        
        registry2 = get_process_registry()
        assert registry1 is registry2


class TestProcessRegistryIntegration:
    """Integration tests for process registry with signal handlers and concurrency."""
    
    def test_signal_handler_integration(self):
        """
        Tests signal handler can access process registry.
        Registry is lazily accessed on signal receipt.
        """
        from src.bot import setup_signal_handlers, create_bot
        import src.utils.process_registry as pr_module
        
        pr_module._process_registry = None
        bot = create_bot()
        
        with patch('src.bot.get_process_registry') as mock_get:
            mock_registry = MagicMock()
            mock_get.return_value = mock_registry
            setup_signal_handlers(bot)
            # Not called until signal received
            assert mock_get.call_count == 0
    
    @pytest.mark.asyncio
    async def test_concurrent_access(self):
        """
        Tests thread safety with concurrent register/unregister operations.
        All processes should be properly unregistered after concurrent ops.
        """
        registry = ProcessRegistry()
        
        async def register_and_unregister(pid: int):
            mock_process = MagicMock()
            mock_process.pid = pid
            await registry.register(mock_process)
            await asyncio.sleep(0.01)
            await registry.unregister(mock_process)
        
        tasks = [register_and_unregister(i) for i in range(10)]
        await asyncio.gather(*tasks)
        
        assert registry.active_count == 0
