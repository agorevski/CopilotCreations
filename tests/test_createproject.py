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
    update_message_with_content,
    read_stream,
    setup_createproject_command,
    _create_project_directory,
    _send_initial_messages,
    _run_copilot_process
)
from src.config import MAX_MESSAGE_LENGTH, PROJECTS_DIR
from src.utils.async_buffer import AsyncOutputBuffer
from src.utils.logging import SessionLogCollector


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
        output_buffer = AsyncOutputBuffer()
        await output_buffer.append("Line 1\n")
        await output_buffer.append("Line 2\n")
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
        output_buffer = AsyncOutputBuffer()
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
        output_buffer = AsyncOutputBuffer()
        await output_buffer.append("test")
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
        output_buffer = AsyncOutputBuffer()
        await output_buffer.append("x" * 10000)
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
        output_buffer = AsyncOutputBuffer()
        await output_buffer.append("test")
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
        output_buffer = AsyncOutputBuffer()
        await output_buffer.append("test")
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
        
        output_buffer = AsyncOutputBuffer()
        await read_stream(mock_stream, output_buffer)
        
        items = await output_buffer.get_list()
        assert len(items) == 2
        assert "Line 1\n" in items
        assert "Line 2\n" in items
    
    @pytest.mark.asyncio
    async def test_handles_unicode(self):
        """Test that unicode is handled correctly."""
        mock_stream = AsyncMock()
        mock_stream.readline = AsyncMock(side_effect=[
            "Hello 世界\n".encode('utf-8'),
            b""
        ])
        
        output_buffer = AsyncOutputBuffer()
        await read_stream(mock_stream, output_buffer)
        
        items = await output_buffer.get_list()
        assert len(items) == 1
        assert "世界" in items[0]
    
    @pytest.mark.asyncio
    async def test_handles_invalid_utf8(self):
        """Test that invalid UTF-8 is handled with replacement."""
        mock_stream = AsyncMock()
        mock_stream.readline = AsyncMock(side_effect=[
            b"\xff\xfe Invalid UTF-8\n",
            b""
        ])
        
        output_buffer = AsyncOutputBuffer()
        await read_stream(mock_stream, output_buffer)
        
        items = await output_buffer.get_list()
        assert len(items) == 1
        # Should contain replacement characters or partial content
        assert "Invalid" in items[0]
    
    @pytest.mark.asyncio
    async def test_empty_stream(self):
        """Test handling of empty stream."""
        mock_stream = AsyncMock()
        mock_stream.readline = AsyncMock(side_effect=[b""])
        
        output_buffer = AsyncOutputBuffer()
        await read_stream(mock_stream, output_buffer)
        
        items = await output_buffer.get_list()
        assert len(items) == 0


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


class TestUpdateMessageWithContent:
    """Tests for the generic update_message_with_content function."""
    
    @pytest.mark.asyncio
    async def test_updates_when_content_changes(self):
        """Test that message is updated when content changes."""
        mock_message = AsyncMock()
        call_count = [0]
        
        def content_generator():
            call_count[0] += 1
            return f"Content {call_count[0]}"
        
        is_running = asyncio.Event()
        is_running.set()
        error_event = asyncio.Event()
        
        async def stop_after_delay():
            await asyncio.sleep(0.15)
            is_running.clear()
        
        await asyncio.gather(
            update_message_with_content(mock_message, content_generator, is_running, error_event),
            stop_after_delay()
        )
        
        # Should have called edit at least once
        assert mock_message.edit.called
    
    @pytest.mark.asyncio
    async def test_stops_on_error_event(self):
        """Test that update stops when error event is set."""
        mock_message = AsyncMock()
        is_running = asyncio.Event()
        is_running.set()
        error_event = asyncio.Event()
        error_event.set()  # Set error immediately
        
        await update_message_with_content(mock_message, lambda: "test", is_running, error_event)
        
        # Should not have called edit since error was set
        assert not mock_message.edit.called


class TestRunCopilotProcess:
    """Tests for _run_copilot_process function."""
    
    @pytest.mark.asyncio
    async def test_run_copilot_process_success(self):
        """Test successful copilot process execution."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)
            session_log = SessionLogCollector("test")
            output_buffer = AsyncOutputBuffer()
            is_running = asyncio.Event()
            is_running.set()
            error_event = asyncio.Event()
            
            with patch('asyncio.create_subprocess_exec', new_callable=AsyncMock) as mock_exec:
                mock_process = AsyncMock()
                mock_process.stdout = AsyncMock()
                mock_process.stdout.readline = AsyncMock(side_effect=[b"output line\n", b""])
                mock_process.wait = AsyncMock(return_value=0)
                mock_process.returncode = 0
                mock_process.pid = 12345
                mock_process.kill = MagicMock()
                mock_exec.return_value = mock_process
                
                with patch('src.commands.createproject.TIMEOUT_SECONDS', 1):
                    with patch('src.commands.createproject.PROGRESS_LOG_INTERVAL_SECONDS', 100):
                        timed_out, error_occurred, error_message, process = await _run_copilot_process(
                            project_path, "test prompt", None, session_log,
                            output_buffer, is_running, error_event
                        )
                
                assert timed_out is False
                assert error_occurred is False
                assert process is not None
    
    @pytest.mark.asyncio
    async def test_run_copilot_process_with_model(self):
        """Test copilot process execution with model specified."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)
            session_log = SessionLogCollector("test")
            output_buffer = AsyncOutputBuffer()
            is_running = asyncio.Event()
            is_running.set()
            error_event = asyncio.Event()
            
            with patch('asyncio.create_subprocess_exec', new_callable=AsyncMock) as mock_exec:
                mock_process = AsyncMock()
                mock_process.stdout = AsyncMock()
                mock_process.stdout.readline = AsyncMock(side_effect=[b""])
                mock_process.wait = AsyncMock(return_value=0)
                mock_process.returncode = 0
                mock_process.pid = 12345
                mock_exec.return_value = mock_process
                
                with patch('src.commands.createproject.TIMEOUT_SECONDS', 1):
                    with patch('src.commands.createproject.PROGRESS_LOG_INTERVAL_SECONDS', 100):
                        await _run_copilot_process(
                            project_path, "test prompt", "gpt-4", session_log,
                            output_buffer, is_running, error_event
                        )
                
                # Check that model was included in command
                call_args = mock_exec.call_args[0]
                assert "--model" in call_args
                assert "gpt-4" in call_args
    
    @pytest.mark.asyncio
    async def test_run_copilot_process_timeout(self):
        """Test copilot process timeout handling."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)
            session_log = SessionLogCollector("test")
            output_buffer = AsyncOutputBuffer()
            is_running = asyncio.Event()
            is_running.set()
            error_event = asyncio.Event()
            
            with patch('asyncio.create_subprocess_exec', new_callable=AsyncMock) as mock_exec:
                mock_process = AsyncMock()
                mock_process.stdout = AsyncMock()
                mock_process.stdout.readline = AsyncMock(side_effect=[b""])
                mock_process.wait = AsyncMock(side_effect=asyncio.TimeoutError())
                mock_process.returncode = -9
                mock_process.pid = 12345
                mock_process.kill = MagicMock()
                mock_exec.return_value = mock_process
                
                with patch('src.commands.createproject.TIMEOUT_SECONDS', 0.01):
                    with patch('src.commands.createproject.PROGRESS_LOG_INTERVAL_SECONDS', 100):
                        timed_out, error_occurred, error_message, process = await _run_copilot_process(
                            project_path, "test prompt", None, session_log,
                            output_buffer, is_running, error_event
                        )
                
                assert timed_out is True
                mock_process.kill.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_run_copilot_process_exception(self):
        """Test copilot process exception handling."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)
            session_log = SessionLogCollector("test")
            output_buffer = AsyncOutputBuffer()
            is_running = asyncio.Event()
            is_running.set()
            error_event = asyncio.Event()
            
            with patch('asyncio.create_subprocess_exec', new_callable=AsyncMock) as mock_exec:
                mock_exec.side_effect = OSError("Command not found")
                
                timed_out, error_occurred, error_message, process = await _run_copilot_process(
                    project_path, "test prompt", None, session_log,
                    output_buffer, is_running, error_event
                )
                
                assert error_occurred is True
                assert error_event.is_set()


class TestCommandValidation:
    """Tests for command input validation."""
    
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
    
    @pytest.mark.asyncio
    async def test_validates_empty_prompt(self, mock_interaction):
        """Test that empty prompt is rejected."""
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
        
        await captured_handler(mock_interaction, "   ", None)
        
        mock_interaction.response.send_message.assert_called_once()
        call_args = str(mock_interaction.response.send_message.call_args)
        assert "empty" in call_args.lower()
    
    @pytest.mark.asyncio
    async def test_validates_long_prompt(self, mock_interaction):
        """Test that overly long prompt is rejected."""
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
        
        long_prompt = "x" * 20000  # Exceeds MAX_PROMPT_LENGTH
        await captured_handler(mock_interaction, long_prompt, None)
        
        mock_interaction.response.send_message.assert_called_once()
        call_args = str(mock_interaction.response.send_message.call_args)
        assert "too long" in call_args.lower()
    
    @pytest.mark.asyncio
    async def test_validates_invalid_model(self, mock_interaction):
        """Test that invalid model name is rejected."""
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
        
        await captured_handler(mock_interaction, "valid prompt", "invalid model!!!")
        
        mock_interaction.response.send_message.assert_called_once()
        call_args = str(mock_interaction.response.send_message.call_args)
        assert "invalid" in call_args.lower()


class TestHelperFunctions:
    """Tests for extracted helper functions."""
    
    @pytest.mark.asyncio
    async def test_create_project_directory(self):
        """Test that _create_project_directory creates a directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch('src.commands.createproject.PROJECTS_DIR', Path(tmpdir)):
                session_log = SessionLogCollector("test_session")
                
                project_path, folder_name = await _create_project_directory("testuser", session_log)
                
                assert project_path.exists()
                assert "testuser" in folder_name
    
    @pytest.mark.asyncio
    async def test_send_initial_messages(self):
        """Test that _send_initial_messages sends two messages."""
        mock_interaction = AsyncMock()
        mock_file_tree_msg = AsyncMock()
        mock_output_msg = AsyncMock()
        
        mock_interaction.followup.send = AsyncMock(return_value=mock_file_tree_msg)
        mock_interaction.channel.send = AsyncMock(return_value=mock_output_msg)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)
            
            file_tree_msg, output_msg = await _send_initial_messages(
                mock_interaction, project_path, None
            )
            
            assert mock_interaction.followup.send.called
            assert mock_interaction.channel.send.called
    
    @pytest.mark.asyncio
    async def test_send_initial_messages_with_model(self):
        """Test that _send_initial_messages includes model info."""
        mock_interaction = AsyncMock()
        mock_file_tree_msg = AsyncMock()
        mock_output_msg = AsyncMock()
        
        mock_interaction.followup.send = AsyncMock(return_value=mock_file_tree_msg)
        mock_interaction.channel.send = AsyncMock(return_value=mock_output_msg)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)
            
            await _send_initial_messages(mock_interaction, project_path, "gpt-4")
            
            # Check that model was included in output message
            call_args = str(mock_interaction.channel.send.call_args)
            assert "gpt-4" in call_args


class TestUpdateFinalMessages:
    """Tests for _update_final_messages function."""
    
    @pytest.mark.asyncio
    async def test_update_final_messages_success(self):
        """Test that _update_final_messages updates both messages."""
        from src.commands.createproject import _update_final_messages
        
        mock_file_tree_msg = AsyncMock()
        mock_output_msg = AsyncMock()
        output_buffer = AsyncOutputBuffer()
        await output_buffer.append("Test output")
        
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            (tmppath / "test.txt").touch()
            
            await _update_final_messages(
                mock_file_tree_msg, mock_output_msg, tmppath, output_buffer, None
            )
            
            assert mock_file_tree_msg.edit.called
            assert mock_output_msg.edit.called
    
    @pytest.mark.asyncio
    async def test_update_final_messages_with_model(self):
        """Test that _update_final_messages includes model info."""
        from src.commands.createproject import _update_final_messages
        
        mock_file_tree_msg = AsyncMock()
        mock_output_msg = AsyncMock()
        output_buffer = AsyncOutputBuffer()
        await output_buffer.append("Test output")
        
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            
            await _update_final_messages(
                mock_file_tree_msg, mock_output_msg, tmppath, output_buffer, "claude-3"
            )
            
            call_args = str(mock_output_msg.edit.call_args)
            assert "claude-3" in call_args
    
    @pytest.mark.asyncio
    async def test_update_final_messages_empty_output(self):
        """Test that _update_final_messages handles empty output."""
        from src.commands.createproject import _update_final_messages
        
        mock_file_tree_msg = AsyncMock()
        mock_output_msg = AsyncMock()
        output_buffer = AsyncOutputBuffer()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            
            await _update_final_messages(
                mock_file_tree_msg, mock_output_msg, tmppath, output_buffer, None
            )
            
            call_args = str(mock_output_msg.edit.call_args)
            assert "no output" in call_args
    
    @pytest.mark.asyncio
    async def test_update_final_messages_handles_exception(self):
        """Test that _update_final_messages handles exceptions gracefully."""
        from src.commands.createproject import _update_final_messages
        
        mock_file_tree_msg = AsyncMock()
        mock_file_tree_msg.edit.side_effect = RuntimeError("Test error")
        mock_output_msg = AsyncMock()
        output_buffer = AsyncOutputBuffer()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            
            # Should not raise exception
            await _update_final_messages(
                mock_file_tree_msg, mock_output_msg, tmppath, output_buffer, None
            )
    
    @pytest.mark.asyncio
    async def test_update_final_messages_truncates_long_content(self):
        """Test that _update_final_messages truncates long output."""
        from src.commands.createproject import _update_final_messages
        
        mock_file_tree_msg = AsyncMock()
        mock_output_msg = AsyncMock()
        output_buffer = AsyncOutputBuffer()
        await output_buffer.append("x" * 10000)  # Very long output
        
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            
            await _update_final_messages(
                mock_file_tree_msg, mock_output_msg, tmppath, output_buffer, None
            )
            
            # Verify content was truncated
            call_args = mock_output_msg.edit.call_args
            if call_args:
                content = call_args.kwargs.get('content', '')
                assert len(content) <= MAX_MESSAGE_LENGTH


class TestHandleGithubIntegration:
    """Tests for _handle_github_integration function."""
    
    @pytest.mark.asyncio
    async def test_github_disabled(self):
        """Test GitHub integration when disabled."""
        from src.commands.createproject import _handle_github_integration
        
        mock_process = MagicMock()
        mock_process.returncode = 0
        session_log = SessionLogCollector("test")
        
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch('src.commands.createproject.GITHUB_ENABLED', False):
                status, success = await _handle_github_integration(
                    Path(tmpdir), "test_folder", "test prompt",
                    False, False, mock_process, session_log
                )
                
                assert success is False
                assert status == ""
    
    @pytest.mark.asyncio
    async def test_github_skipped_on_timeout(self):
        """Test GitHub skipped when process timed out."""
        from src.commands.createproject import _handle_github_integration
        
        mock_process = MagicMock()
        mock_process.returncode = 0
        session_log = SessionLogCollector("test")
        
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch('src.commands.createproject.GITHUB_ENABLED', True):
                status, success = await _handle_github_integration(
                    Path(tmpdir), "test_folder", "test prompt",
                    True, False, mock_process, session_log  # timed_out=True
                )
                
                assert success is False
                assert "Skipped" in status
    
    @pytest.mark.asyncio
    async def test_github_skipped_on_error(self):
        """Test GitHub skipped when error occurred."""
        from src.commands.createproject import _handle_github_integration
        
        mock_process = MagicMock()
        mock_process.returncode = 0
        session_log = SessionLogCollector("test")
        
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch('src.commands.createproject.GITHUB_ENABLED', True):
                status, success = await _handle_github_integration(
                    Path(tmpdir), "test_folder", "test prompt",
                    False, True, mock_process, session_log  # error_occurred=True
                )
                
                assert success is False
                assert "Skipped" in status
    
    @pytest.mark.asyncio
    async def test_github_skipped_on_nonzero_exit(self):
        """Test GitHub skipped when process exit code is non-zero."""
        from src.commands.createproject import _handle_github_integration
        
        mock_process = MagicMock()
        mock_process.returncode = 1  # Non-zero exit
        session_log = SessionLogCollector("test")
        
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch('src.commands.createproject.GITHUB_ENABLED', True):
                status, success = await _handle_github_integration(
                    Path(tmpdir), "test_folder", "test prompt",
                    False, False, mock_process, session_log
                )
                
                assert success is False
                assert "Skipped" in status
    
    @pytest.mark.asyncio
    async def test_github_not_configured(self):
        """Test GitHub when enabled but not configured."""
        from src.commands.createproject import _handle_github_integration
        
        mock_process = MagicMock()
        mock_process.returncode = 0
        session_log = SessionLogCollector("test")
        
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch('src.commands.createproject.GITHUB_ENABLED', True):
                with patch('src.commands.createproject.github_manager') as mock_manager:
                    mock_manager.is_configured.return_value = False
                    
                    status, success = await _handle_github_integration(
                        Path(tmpdir), "test_folder", "test prompt",
                        False, False, mock_process, session_log
                    )
                    
                    assert success is False
                    assert "Not configured" in status
    
    @pytest.mark.asyncio
    async def test_github_success(self):
        """Test GitHub integration success."""
        from src.commands.createproject import _handle_github_integration
        
        mock_process = MagicMock()
        mock_process.returncode = 0
        session_log = SessionLogCollector("test")
        
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch('src.commands.createproject.GITHUB_ENABLED', True):
                with patch('src.commands.createproject.github_manager') as mock_manager:
                    mock_manager.is_configured.return_value = True
                    mock_manager.create_and_push_project.return_value = (
                        True, "Created successfully", "https://github.com/test/repo"
                    )
                    
                    status, success = await _handle_github_integration(
                        Path(tmpdir), "test_folder", "test prompt",
                        False, False, mock_process, session_log
                    )
                    
                    assert success is True
                    assert "View Repository" in status
    
    @pytest.mark.asyncio
    async def test_github_failure(self):
        """Test GitHub integration failure."""
        from src.commands.createproject import _handle_github_integration
        
        mock_process = MagicMock()
        mock_process.returncode = 0
        session_log = SessionLogCollector("test")
        
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch('src.commands.createproject.GITHUB_ENABLED', True):
                with patch('src.commands.createproject.github_manager') as mock_manager:
                    mock_manager.is_configured.return_value = True
                    mock_manager.create_and_push_project.return_value = (
                        False, "Failed to create", None
                    )
                    
                    status, success = await _handle_github_integration(
                        Path(tmpdir), "test_folder", "test prompt",
                        False, False, mock_process, session_log
                    )
                    
                    assert success is False
                    assert "⚠️" in status


class TestCleanupProjectDirectory:
    """Tests for _cleanup_project_directory function."""
    
    def test_cleanup_success(self):
        """Test successful cleanup of project directory."""
        from src.commands.createproject import _cleanup_project_directory
        
        session_log = SessionLogCollector("test")
        
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir) / "test_project"
            project_path.mkdir()
            (project_path / "test.txt").touch()
            
            result = _cleanup_project_directory(project_path, session_log)
            
            assert result is True
            assert not project_path.exists()
    
    def test_cleanup_nonexistent_directory(self):
        """Test cleanup of non-existent directory."""
        from src.commands.createproject import _cleanup_project_directory
        
        session_log = SessionLogCollector("test")
        project_path = Path("/nonexistent/path/that/does/not/exist")
        
        result = _cleanup_project_directory(project_path, session_log)
        
        assert result is False
    
    def test_cleanup_handles_exception(self):
        """Test cleanup handles exceptions."""
        from src.commands.createproject import _cleanup_project_directory
        
        session_log = SessionLogCollector("test")
        
        # Create a temp directory first, then patch inside the function call
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir) / "test_project"
            project_path.mkdir()
            
            with patch.object(shutil, 'rmtree') as mock_rmtree:
                mock_rmtree.side_effect = PermissionError("Access denied")
                
                result = _cleanup_project_directory(project_path, session_log)
                
                assert result is False
            
            # Clean up manually since rmtree was mocked
            if project_path.exists():
                shutil.rmtree(project_path)


class TestSendSummary:
    """Tests for _send_summary function."""
    
    @pytest.mark.asyncio
    async def test_send_summary_success(self):
        """Test sending summary on successful completion."""
        from src.commands.createproject import _send_summary
        
        mock_interaction = AsyncMock()
        mock_interaction.channel.send = AsyncMock()
        mock_interaction.user.mention = "@testuser"
        
        session_log = SessionLogCollector("test")
        mock_process = MagicMock()
        mock_process.returncode = 0
        output_buffer = AsyncOutputBuffer()
        await output_buffer.append("Test output")
        
        await _send_summary(
            mock_interaction, session_log, "test_folder", "test prompt", None,
            False, False, "", mock_process, 5, 2, "", output_buffer
        )
        
        assert mock_interaction.channel.send.called
        call_args = str(mock_interaction.channel.send.call_args)
        assert "COMPLETED SUCCESSFULLY" in call_args
    
    @pytest.mark.asyncio
    async def test_send_summary_timeout(self):
        """Test sending summary on timeout."""
        from src.commands.createproject import _send_summary
        
        mock_interaction = AsyncMock()
        mock_interaction.channel.send = AsyncMock()
        mock_interaction.user.mention = "@testuser"
        
        session_log = SessionLogCollector("test")
        mock_process = MagicMock()
        mock_process.returncode = -9
        output_buffer = AsyncOutputBuffer()
        
        await _send_summary(
            mock_interaction, session_log, "test_folder", "test prompt", None,
            True, False, "", mock_process, 0, 0, "", output_buffer  # timed_out=True
        )
        
        call_args = str(mock_interaction.channel.send.call_args)
        assert "TIMED OUT" in call_args
    
    @pytest.mark.asyncio
    async def test_send_summary_error(self):
        """Test sending summary on error."""
        from src.commands.createproject import _send_summary
        
        mock_interaction = AsyncMock()
        mock_interaction.channel.send = AsyncMock()
        mock_interaction.user.mention = "@testuser"
        
        session_log = SessionLogCollector("test")
        mock_process = None
        output_buffer = AsyncOutputBuffer()
        
        await _send_summary(
            mock_interaction, session_log, "test_folder", "test prompt", None,
            False, True, "Error occurred", mock_process, 0, 0, "", output_buffer  # error_occurred=True
        )
        
        call_args = str(mock_interaction.channel.send.call_args)
        assert "ERROR" in call_args
    
    @pytest.mark.asyncio
    async def test_send_summary_nonzero_exit(self):
        """Test sending summary on non-zero exit code."""
        from src.commands.createproject import _send_summary
        
        mock_interaction = AsyncMock()
        mock_interaction.channel.send = AsyncMock()
        mock_interaction.user.mention = "@testuser"
        
        session_log = SessionLogCollector("test")
        mock_process = MagicMock()
        mock_process.returncode = 1
        output_buffer = AsyncOutputBuffer()
        
        await _send_summary(
            mock_interaction, session_log, "test_folder", "test prompt", "gpt-4",
            False, False, "", mock_process, 3, 1, "", output_buffer
        )
        
        call_args = str(mock_interaction.channel.send.call_args)
        assert "EXIT CODE 1" in call_args
    
    @pytest.mark.asyncio
    async def test_send_summary_with_github_status(self):
        """Test sending summary with GitHub status."""
        from src.commands.createproject import _send_summary
        
        mock_interaction = AsyncMock()
        mock_interaction.channel.send = AsyncMock()
        mock_interaction.user.mention = "@testuser"
        
        session_log = SessionLogCollector("test")
        mock_process = MagicMock()
        mock_process.returncode = 0
        output_buffer = AsyncOutputBuffer()
        
        github_status = "\n**🐙 GitHub:** [View Repository](https://github.com/test/repo)"
        
        await _send_summary(
            mock_interaction, session_log, "test_folder", "test prompt", None,
            False, False, "", mock_process, 5, 2, github_status, output_buffer
        )
        
        call_args = str(mock_interaction.channel.send.call_args)
        assert "GitHub" in call_args
    
    @pytest.mark.asyncio
    async def test_send_summary_handles_send_exception(self):
        """Test sending summary handles exception and falls back."""
        from src.commands.createproject import _send_summary
        import discord
        
        mock_interaction = AsyncMock()
        # First call raises, second succeeds
        mock_interaction.channel.send = AsyncMock(
            side_effect=[RuntimeError("File too large"), None]
        )
        mock_interaction.user.mention = "@testuser"
        
        session_log = SessionLogCollector("test")
        mock_process = MagicMock()
        mock_process.returncode = 0
        output_buffer = AsyncOutputBuffer()
        
        # Should not raise exception
        await _send_summary(
            mock_interaction, session_log, "test_folder", "test prompt", None,
            False, False, "", mock_process, 5, 2, "", output_buffer
        )
        
        # Should have been called twice (once with file, once without)
        assert mock_interaction.channel.send.call_count == 2
    
    @pytest.mark.asyncio
    async def test_send_summary_no_process(self):
        """Test sending summary when process is None."""
        from src.commands.createproject import _send_summary
        
        mock_interaction = AsyncMock()
        mock_interaction.channel.send = AsyncMock()
        mock_interaction.user.mention = "@testuser"
        
        session_log = SessionLogCollector("test")
        output_buffer = AsyncOutputBuffer()
        
        await _send_summary(
            mock_interaction, session_log, "test_folder", "test prompt", None,
            False, False, "", None, 0, 0, "", output_buffer  # process=None
        )
        
        call_args = str(mock_interaction.channel.send.call_args)
        assert "unknown" in call_args
    
    @pytest.mark.asyncio
    async def test_send_summary_includes_copilot_output_in_log(self):
        """Test that copilot output is included in the log file attachment."""
        from src.commands.createproject import _send_summary
        
        mock_interaction = AsyncMock()
        mock_interaction.channel.send = AsyncMock()
        mock_interaction.user.mention = "@testuser"
        
        session_log = SessionLogCollector("test")
        mock_process = MagicMock()
        mock_process.returncode = 0
        
        copilot_output = "Creating files...\nGenerated main.py\nDone!"
        output_buffer = AsyncOutputBuffer()
        await output_buffer.append(copilot_output)
        
        await _send_summary(
            mock_interaction, session_log, "test_folder", "test prompt", None,
            False, False, "", mock_process, 5, 2, "", output_buffer
        )
        
        # Check that the log file contains the copilot output
        call_kwargs = mock_interaction.channel.send.call_args
        assert call_kwargs is not None
        # The file is passed as a keyword argument
        file_arg = call_kwargs.kwargs.get('file')
        assert file_arg is not None
        
        # Read the file content
        file_content = file_arg.fp.read().decode('utf-8')
        assert "## Copilot Output" in file_content
        assert "Creating files..." in file_content
        assert "Generated main.py" in file_content
        assert "Done!" in file_content
