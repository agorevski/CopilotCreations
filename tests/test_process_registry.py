"""
Tests for process registry module.
"""

import asyncio
import pytest
from unittest.mock import MagicMock, patch, AsyncMock

from src.utils.process_registry import ProcessRegistry, get_process_registry


class TestProcessRegistry:
    """Tests for ProcessRegistry class."""
    
    def test_process_registry_init(self):
        """Test ProcessRegistry initialization."""
        registry = ProcessRegistry()
        assert registry._processes == set()
        assert registry.active_count == 0
    
    @pytest.mark.asyncio
    async def test_register_process(self):
        """Test registering a process."""
        registry = ProcessRegistry()
        mock_process = MagicMock()
        mock_process.pid = 12345
        
        await registry.register(mock_process)
        
        assert mock_process in registry._processes
        assert registry.active_count == 1
    
    @pytest.mark.asyncio
    async def test_register_multiple_processes(self):
        """Test registering multiple processes."""
        registry = ProcessRegistry()
        mock_process1 = MagicMock()
        mock_process1.pid = 12345
        mock_process2 = MagicMock()
        mock_process2.pid = 12346
        
        await registry.register(mock_process1)
        await registry.register(mock_process2)
        
        assert registry.active_count == 2
        assert mock_process1 in registry._processes
        assert mock_process2 in registry._processes
    
    @pytest.mark.asyncio
    async def test_unregister_process(self):
        """Test unregistering a process."""
        registry = ProcessRegistry()
        mock_process = MagicMock()
        mock_process.pid = 12345
        
        await registry.register(mock_process)
        assert registry.active_count == 1
        
        await registry.unregister(mock_process)
        assert registry.active_count == 0
        assert mock_process not in registry._processes
    
    @pytest.mark.asyncio
    async def test_unregister_nonexistent_process(self):
        """Test unregistering a process that was never registered."""
        registry = ProcessRegistry()
        mock_process = MagicMock()
        mock_process.pid = 12345
        
        # Should not raise an error
        await registry.unregister(mock_process)
        assert registry.active_count == 0
    
    @pytest.mark.asyncio
    async def test_kill_all_empty(self):
        """Test kill_all with no registered processes."""
        registry = ProcessRegistry()
        
        # Should not raise an error
        await registry.kill_all()
        assert registry.active_count == 0
    
    @pytest.mark.asyncio
    async def test_kill_all_running_processes(self):
        """Test kill_all kills all running processes."""
        registry = ProcessRegistry()
        
        # Create mock processes that are still running
        mock_process1 = MagicMock()
        mock_process1.pid = 12345
        mock_process1.returncode = None  # Still running
        mock_process1.kill = MagicMock()
        mock_process1.wait = AsyncMock()
        
        mock_process2 = MagicMock()
        mock_process2.pid = 12346
        mock_process2.returncode = None  # Still running
        mock_process2.kill = MagicMock()
        mock_process2.wait = AsyncMock()
        
        await registry.register(mock_process1)
        await registry.register(mock_process2)
        
        await registry.kill_all()
        
        mock_process1.kill.assert_called_once()
        mock_process2.kill.assert_called_once()
        assert registry.active_count == 0
    
    @pytest.mark.asyncio
    async def test_kill_all_skips_completed_processes(self):
        """Test kill_all skips processes that have already completed."""
        registry = ProcessRegistry()
        
        # Create a mock process that has already completed
        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_process.returncode = 0  # Already completed
        mock_process.kill = MagicMock()
        mock_process.wait = AsyncMock()
        
        await registry.register(mock_process)
        
        await registry.kill_all()
        
        # kill should NOT be called since process already completed
        mock_process.kill.assert_not_called()
        assert registry.active_count == 0
    
    @pytest.mark.asyncio
    async def test_kill_all_handles_timeout(self):
        """Test kill_all handles timeout when waiting for process."""
        registry = ProcessRegistry()
        
        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_process.returncode = None
        mock_process.kill = MagicMock()
        # Simulate a process that never terminates
        mock_process.wait = AsyncMock(side_effect=asyncio.TimeoutError())
        
        await registry.register(mock_process)
        
        # Should not raise, just log warning
        await registry.kill_all()
        
        mock_process.kill.assert_called_once()
        assert registry.active_count == 0
    
    @pytest.mark.asyncio
    async def test_kill_all_handles_exception(self):
        """Test kill_all handles exceptions during kill."""
        registry = ProcessRegistry()
        
        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_process.returncode = None
        mock_process.kill = MagicMock(side_effect=Exception("Kill failed"))
        mock_process.wait = AsyncMock()
        
        await registry.register(mock_process)
        
        # Should not raise, just log error
        await registry.kill_all()
        
        assert registry.active_count == 0
    
    def test_kill_all_sync_empty(self):
        """Test kill_all_sync with no registered processes."""
        registry = ProcessRegistry()
        
        # Should not raise an error
        registry.kill_all_sync()
        assert registry.active_count == 0
    
    def test_kill_all_sync_running_processes(self):
        """Test kill_all_sync kills all running processes."""
        registry = ProcessRegistry()
        
        mock_process1 = MagicMock()
        mock_process1.pid = 12345
        mock_process1.returncode = None  # Still running
        mock_process1.kill = MagicMock()
        
        mock_process2 = MagicMock()
        mock_process2.pid = 12346
        mock_process2.returncode = None  # Still running
        mock_process2.kill = MagicMock()
        
        registry._processes.add(mock_process1)
        registry._processes.add(mock_process2)
        
        registry.kill_all_sync()
        
        mock_process1.kill.assert_called_once()
        mock_process2.kill.assert_called_once()
        assert registry.active_count == 0
    
    def test_kill_all_sync_skips_completed_processes(self):
        """Test kill_all_sync skips already-completed processes."""
        registry = ProcessRegistry()
        
        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_process.returncode = 0  # Already completed
        mock_process.kill = MagicMock()
        
        registry._processes.add(mock_process)
        
        registry.kill_all_sync()
        
        mock_process.kill.assert_not_called()
        assert registry.active_count == 0
    
    def test_kill_all_sync_handles_exception(self):
        """Test kill_all_sync handles exceptions during kill."""
        registry = ProcessRegistry()
        
        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_process.returncode = None
        mock_process.kill = MagicMock(side_effect=Exception("Kill failed"))
        
        registry._processes.add(mock_process)
        
        # Should not raise, just log error
        registry.kill_all_sync()
        
        assert registry.active_count == 0
    
    def test_active_count_property(self):
        """Test active_count property returns correct count."""
        registry = ProcessRegistry()
        
        mock_process1 = MagicMock()
        mock_process2 = MagicMock()
        mock_process3 = MagicMock()
        
        registry._processes.add(mock_process1)
        assert registry.active_count == 1
        
        registry._processes.add(mock_process2)
        assert registry.active_count == 2
        
        registry._processes.add(mock_process3)
        assert registry.active_count == 3
        
        registry._processes.discard(mock_process2)
        assert registry.active_count == 2


class TestGetProcessRegistry:
    """Tests for get_process_registry function."""
    
    def test_get_process_registry_returns_instance(self):
        """Test get_process_registry returns a ProcessRegistry instance."""
        # Reset the global registry first
        import src.utils.process_registry as pr_module
        pr_module._process_registry = None
        
        registry = get_process_registry()
        
        assert isinstance(registry, ProcessRegistry)
    
    def test_get_process_registry_singleton(self):
        """Test get_process_registry returns the same instance."""
        # Reset the global registry first
        import src.utils.process_registry as pr_module
        pr_module._process_registry = None
        
        registry1 = get_process_registry()
        registry2 = get_process_registry()
        
        assert registry1 is registry2


class TestProcessRegistryIntegration:
    """Integration tests for process registry with signal handlers."""
    
    def test_signal_handler_uses_process_registry(self):
        """Test that signal handler can access and use process registry."""
        from src.bot import setup_signal_handlers, create_bot
        import src.utils.process_registry as pr_module
        
        # Reset the global registry
        pr_module._process_registry = None
        
        bot = create_bot()
        
        # Mock the process registry
        with patch('src.bot.get_process_registry') as mock_get_registry:
            mock_registry = MagicMock()
            mock_get_registry.return_value = mock_registry
            
            setup_signal_handlers(bot)
            
            # The signal handler is set up; we verify the registry is accessible
            assert mock_get_registry.call_count == 0  # Not called until signal received
    
    @pytest.mark.asyncio
    async def test_process_registry_concurrent_access(self):
        """Test process registry handles concurrent access correctly."""
        registry = ProcessRegistry()
        
        async def register_and_unregister(pid: int):
            mock_process = MagicMock()
            mock_process.pid = pid
            await registry.register(mock_process)
            await asyncio.sleep(0.01)  # Small delay
            await registry.unregister(mock_process)
        
        # Run multiple concurrent operations
        tasks = [register_and_unregister(i) for i in range(10)]
        await asyncio.gather(*tasks)
        
        # All processes should be unregistered
        assert registry.active_count == 0
