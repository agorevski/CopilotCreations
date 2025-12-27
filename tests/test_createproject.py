"""
Tests for createproject command.
"""

import asyncio
import pytest
from unittest.mock import MagicMock, patch, AsyncMock, PropertyMock
from pathlib import Path
import tempfile
import io
import shutil

from src.commands.createproject import (
    update_file_tree_message,
    update_output_message,
    read_stream,
    setup_createproject_command
)
from src.config import MAX_MESSAGE_LENGTH, PROJECTS_DIR


class TestUpdateFileTreeMessage:
    """Tests for update_file_tree_message function."""
    
    @pytest.mark.asyncio
    async def test_updates_when_content_changes(self):
        """Test that message is updated when tree content changes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            
            mock_message = AsyncMock()
            is_running = asyncio.Event()
            is_running.set()
            error_event = asyncio.Event()
            
            # Create a file to generate tree content
            (tmppath / "test.txt").touch()
            
            # Run for a short time then stop
            async def stop_after_delay():
                await asyncio.sleep(0.1)
                is_running.clear()
            
            await asyncio.gather(
                update_file_tree_message(mock_message, tmppath, is_running, error_event),
                stop_after_delay()
            )
            
            # Verify message.edit was called
            assert mock_message.edit.called
    
    @pytest.mark.asyncio
    async def test_stops_on_error_event(self):
        """Test that update stops when error event is set."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_message = AsyncMock()
            is_running = asyncio.Event()
            is_running.set()
            error_event = asyncio.Event()
            error_event.set()  # Set error immediately
            
            # Should return quickly without updating
            await update_file_tree_message(mock_message, Path(tmpdir), is_running, error_event)
            
            # Should not have called edit since error was set
            assert not mock_message.edit.called
    
    @pytest.mark.asyncio
    async def test_handles_http_exception(self):
        """Test that HTTP exceptions are handled gracefully."""
        import discord
        
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            (tmppath / "test.txt").touch()
            
            mock_message = AsyncMock()
            mock_message.edit.side_effect = discord.errors.HTTPException(
                MagicMock(), "Rate limited"
            )
            is_running = asyncio.Event()
            is_running.set()
            error_event = asyncio.Event()
            
            async def stop_after_delay():
                await asyncio.sleep(0.1)
                is_running.clear()
            
            # Should not raise exception
            await asyncio.gather(
                update_file_tree_message(mock_message, tmppath, is_running, error_event),
                stop_after_delay()
            )
    
    @pytest.mark.asyncio
    async def test_skips_update_when_content_unchanged(self):
        """Test that no update is sent when content hasn't changed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            (tmppath / "static.txt").touch()
            
            mock_message = AsyncMock()
            is_running = asyncio.Event()
            is_running.set()
            error_event = asyncio.Event()
            
            call_count = [0]
            original_edit = mock_message.edit
            
            async def counting_edit(*args, **kwargs):
                call_count[0] += 1
                return await original_edit(*args, **kwargs)
            
            mock_message.edit = counting_edit
            
            async def stop_after_delay():
                await asyncio.sleep(0.15)  # Enough for 2 iterations
                is_running.clear()
            
            await asyncio.gather(
                update_file_tree_message(mock_message, tmppath, is_running, error_event),
                stop_after_delay()
            )
            
            # Should only call edit once since content doesn't change
            assert call_count[0] == 1
    
    @pytest.mark.asyncio
    async def test_truncates_long_content(self):
        """Test that long content is truncated."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            
            # Create many files to generate long tree
            for i in range(100):
                (tmppath / f"file_{i:04d}.txt").touch()
            
            mock_message = AsyncMock()
            is_running = asyncio.Event()
            is_running.set()
            error_event = asyncio.Event()
            
            async def stop_after_delay():
                await asyncio.sleep(0.1)
                is_running.clear()
            
            await asyncio.gather(
                update_file_tree_message(mock_message, tmppath, is_running, error_event),
                stop_after_delay()
            )
            
            # Check that edit was called with content <= MAX_MESSAGE_LENGTH
            call_args = mock_message.edit.call_args
            if call_args:
                content = call_args.kwargs.get('content', '')
                assert len(content) <= MAX_MESSAGE_LENGTH
    
    @pytest.mark.asyncio
    async def test_handles_generic_exception(self):
        """Test that generic exceptions are handled gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            (tmppath / "test.txt").touch()
            
            mock_message = AsyncMock()
            mock_message.edit.side_effect = RuntimeError("Unexpected error")
            is_running = asyncio.Event()
            is_running.set()
            error_event = asyncio.Event()
            
            async def stop_after_delay():
                await asyncio.sleep(0.1)
                is_running.clear()
            
            # Should not raise exception
            await asyncio.gather(
                update_file_tree_message(mock_message, tmppath, is_running, error_event),
                stop_after_delay()
            )


class TestUpdateOutputMessage:
    """Tests for update_output_message function."""
    
    @pytest.mark.asyncio
    async def test_updates_with_buffer_content(self):
        """Test that output message updates with buffer content."""
        mock_message = AsyncMock()
        output_buffer = ["Line 1\n", "Line 2\n"]
        is_running = asyncio.Event()
        is_running.set()
        error_event = asyncio.Event()
        
        async def stop_after_delay():
            await asyncio.sleep(0.1)
            is_running.clear()
        
        await asyncio.gather(
            update_output_message(mock_message, output_buffer, is_running, error_event),
            stop_after_delay()
        )
        
        assert mock_message.edit.called
        # Check that the content includes buffer text
        call_args = mock_message.edit.call_args
        assert "Line 1" in str(call_args) or "Line 2" in str(call_args)
    
    @pytest.mark.asyncio
    async def test_shows_waiting_message_when_empty(self):
        """Test that waiting message is shown for empty buffer."""
        mock_message = AsyncMock()
        output_buffer = []
        is_running = asyncio.Event()
        is_running.set()
        error_event = asyncio.Event()
        
        async def stop_after_delay():
            await asyncio.sleep(0.1)
            is_running.clear()
        
        await asyncio.gather(
            update_output_message(mock_message, output_buffer, is_running, error_event),
            stop_after_delay()
        )
        
        assert mock_message.edit.called
        call_args = str(mock_message.edit.call_args)
        assert "waiting for output" in call_args
    
    @pytest.mark.asyncio
    async def test_handles_http_exception(self):
        """Test that HTTP exceptions are handled gracefully."""
        import discord
        
        mock_message = AsyncMock()
        mock_message.edit.side_effect = discord.errors.HTTPException(
            MagicMock(), "Rate limited"
        )
        output_buffer = ["test"]
        is_running = asyncio.Event()
        is_running.set()
        error_event = asyncio.Event()
        
        async def stop_after_delay():
            await asyncio.sleep(0.1)
            is_running.clear()
        
        # Should not raise exception
        await asyncio.gather(
            update_output_message(mock_message, output_buffer, is_running, error_event),
            stop_after_delay()
        )
    
    @pytest.mark.asyncio
    async def test_truncates_long_output(self):
        """Test that long output is truncated."""
        mock_message = AsyncMock()
        # Create very long output
        output_buffer = ["x" * 10000]
        is_running = asyncio.Event()
        is_running.set()
        error_event = asyncio.Event()
        
        async def stop_after_delay():
            await asyncio.sleep(0.1)
            is_running.clear()
        
        await asyncio.gather(
            update_output_message(mock_message, output_buffer, is_running, error_event),
            stop_after_delay()
        )
        
        # Check that edit was called with content <= MAX_MESSAGE_LENGTH
        call_args = mock_message.edit.call_args
        if call_args:
            content = call_args.kwargs.get('content', '')
            assert len(content) <= MAX_MESSAGE_LENGTH
    
    @pytest.mark.asyncio
    async def test_stops_on_error_event(self):
        """Test that update stops when error event is set."""
        mock_message = AsyncMock()
        output_buffer = ["test"]
        is_running = asyncio.Event()
        is_running.set()
        error_event = asyncio.Event()
        error_event.set()  # Set error immediately
        
        await update_output_message(mock_message, output_buffer, is_running, error_event)
        
        assert not mock_message.edit.called
    
    @pytest.mark.asyncio
    async def test_handles_generic_exception(self):
        """Test that generic exceptions are handled gracefully."""
        mock_message = AsyncMock()
        mock_message.edit.side_effect = RuntimeError("Unexpected error")
        output_buffer = ["test"]
        is_running = asyncio.Event()
        is_running.set()
        error_event = asyncio.Event()
        
        async def stop_after_delay():
            await asyncio.sleep(0.1)
            is_running.clear()
        
        # Should not raise exception
        await asyncio.gather(
            update_output_message(mock_message, output_buffer, is_running, error_event),
            stop_after_delay()
        )


class TestReadStream:
    """Tests for read_stream function."""
    
    @pytest.mark.asyncio
    async def test_reads_lines_to_buffer(self):
        """Test that lines are read into buffer."""
        # Create a mock stream
        mock_stream = AsyncMock()
        mock_stream.readline = AsyncMock(side_effect=[
            b"Line 1\n",
            b"Line 2\n",
            b""  # Empty signals EOF
        ])
        
        output_buffer = []
        await read_stream(mock_stream, output_buffer)
        
        assert len(output_buffer) == 2
        assert "Line 1\n" in output_buffer
        assert "Line 2\n" in output_buffer
    
    @pytest.mark.asyncio
    async def test_handles_unicode(self):
        """Test that unicode is handled correctly."""
        mock_stream = AsyncMock()
        mock_stream.readline = AsyncMock(side_effect=[
            "Hello 世界\n".encode('utf-8'),
            b""
        ])
        
        output_buffer = []
        await read_stream(mock_stream, output_buffer)
        
        assert len(output_buffer) == 1
        assert "世界" in output_buffer[0]
    
    @pytest.mark.asyncio
    async def test_handles_invalid_utf8(self):
        """Test that invalid UTF-8 is handled with replacement."""
        mock_stream = AsyncMock()
        mock_stream.readline = AsyncMock(side_effect=[
            b"\xff\xfe Invalid UTF-8\n",
            b""
        ])
        
        output_buffer = []
        await read_stream(mock_stream, output_buffer)
        
        assert len(output_buffer) == 1
        # Should contain replacement characters or partial content
        assert "Invalid" in output_buffer[0]
    
    @pytest.mark.asyncio
    async def test_empty_stream(self):
        """Test handling of empty stream."""
        mock_stream = AsyncMock()
        mock_stream.readline = AsyncMock(side_effect=[b""])
        
        output_buffer = []
        await read_stream(mock_stream, output_buffer)
        
        assert len(output_buffer) == 0


class TestSetupCreateprojectCommand:
    """Tests for setup_createproject_command function."""
    
    def test_registers_command(self):
        """Test that command is registered on bot."""
        mock_bot = MagicMock()
        mock_bot.tree = MagicMock()
        mock_bot.tree.command = MagicMock(return_value=lambda f: f)
        
        result = setup_createproject_command(mock_bot)
        
        # The decorator should have been called
        mock_bot.tree.command.assert_called_once()
        # Should return the command function
        assert callable(result)
    
    def test_command_has_correct_name(self):
        """Test that command is registered with correct name."""
        mock_bot = MagicMock()
        mock_bot.tree = MagicMock()
        mock_bot.tree.command = MagicMock(return_value=lambda f: f)
        
        setup_createproject_command(mock_bot)
        
        call_kwargs = mock_bot.tree.command.call_args.kwargs
        assert call_kwargs.get('name') == 'createproject'
    
    def test_command_has_description(self):
        """Test that command has a description."""
        mock_bot = MagicMock()
        mock_bot.tree = MagicMock()
        mock_bot.tree.command = MagicMock(return_value=lambda f: f)
        
        setup_createproject_command(mock_bot)
        
        call_kwargs = mock_bot.tree.command.call_args.kwargs
        assert 'description' in call_kwargs
        assert len(call_kwargs['description']) > 0


class TestCreateprojectCommandHandler:
    """Integration tests for the createproject command handler."""
    
    @pytest.fixture
    def mock_interaction(self):
        """Create a mock Discord interaction."""
        interaction = AsyncMock()
        interaction.response = AsyncMock()
        interaction.followup = AsyncMock()
        interaction.channel = AsyncMock()
        interaction.user = MagicMock()
        interaction.user.name = "testuser"
        interaction.user.mention = "@testuser"
        return interaction
    
    @pytest.fixture
    def temp_projects_dir(self):
        """Create a temporary projects directory."""
        tmpdir = tempfile.mkdtemp()
        yield Path(tmpdir)
        shutil.rmtree(tmpdir, ignore_errors=True)
    
    @pytest.mark.asyncio
    async def test_command_defers_response(self, mock_interaction):
        """Test that command defers the response."""
        mock_bot = MagicMock()
        captured_handler = None
        
        def capture_command(*args, **kwargs):
            def decorator(func):
                nonlocal captured_handler
                captured_handler = func
                return func
            return decorator
        
        mock_bot.tree.command = capture_command
        setup_createproject_command(mock_bot)
        
        # Mock the subprocess to fail quickly
        with patch('src.commands.createproject.PROJECTS_DIR') as mock_dir:
            mock_dir.__truediv__ = MagicMock(return_value=Path("/nonexistent"))
            
            with patch('asyncio.create_subprocess_exec', new_callable=AsyncMock) as mock_exec:
                mock_process = AsyncMock()
                mock_process.stdout = AsyncMock()
                mock_process.stdout.readline = AsyncMock(return_value=b"")
                mock_process.wait = AsyncMock(return_value=0)
                mock_process.returncode = 0
                mock_process.pid = 12345
                mock_exec.return_value = mock_process
                
                with patch('pathlib.Path.mkdir'):
                    # Run but expect early return due to mocking complexity
                    try:
                        await captured_handler(mock_interaction, "test prompt", None)
                    except Exception:
                        pass  # Expected due to complex mocking
        
        # Verify defer was called
        mock_interaction.response.defer.assert_called_once()
