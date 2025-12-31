"""
Tests for session commands (startproject, buildproject, cancelprompt).
"""

import asyncio
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from pathlib import Path
import tempfile


class TestSetupSessionCommands:
    """Tests for setup_session_commands function."""
    
    def test_registers_three_commands(self):
        """Test that three commands are registered."""
        from src.commands.session_commands import setup_session_commands
        
        mock_bot = MagicMock()
        mock_bot.tree = MagicMock()
        
        captured_commands = []
        
        def mock_command(*args, **kwargs):
            def decorator(func):
                captured_commands.append((kwargs.get('name'), func))
                return func
            return decorator
        
        mock_bot.tree.command = mock_command
        
        startproject, buildproject, cancelprompt = setup_session_commands(mock_bot)
        
        command_names = [name for name, _ in captured_commands]
        assert 'startproject' in command_names
        assert 'buildproject' in command_names
        assert 'cancelprompt' in command_names
    
    def test_returns_callable_functions(self):
        """Test that returned functions are callable."""
        from src.commands.session_commands import setup_session_commands
        
        mock_bot = MagicMock()
        mock_bot.tree.command = MagicMock(return_value=lambda f: f)
        
        startproject, buildproject, cancelprompt = setup_session_commands(mock_bot)
        
        assert callable(startproject)
        assert callable(buildproject)
        assert callable(cancelprompt)


class TestStartprojectCommand:
    """Tests for the startproject command."""
    
    @pytest.fixture
    def mock_interaction(self):
        """Create a mock Discord interaction."""
        interaction = AsyncMock()
        interaction.response = AsyncMock()
        interaction.followup = AsyncMock()
        interaction.channel = AsyncMock()
        interaction.user = MagicMock()
        interaction.user.id = 12345
        interaction.user.name = "testuser"
        interaction.channel.id = 67890
        return interaction
    
    @pytest.mark.asyncio
    async def test_defers_response(self, mock_interaction):
        """Test that command defers the response."""
        mock_sm = MagicMock()
        mock_sm.get_session = AsyncMock(return_value=None)
        mock_session = MagicMock()
        mock_session.add_bot_message_id = MagicMock()
        mock_sm.start_session = AsyncMock(return_value=mock_session)
        
        mock_rs = MagicMock()
        mock_rs.is_configured.return_value = False
        
        mock_msg = AsyncMock()
        mock_msg.id = 111
        mock_interaction.followup.send = AsyncMock(return_value=mock_msg)
        
        with patch('src.commands.session_commands.get_session_manager', return_value=mock_sm):
            with patch('src.commands.session_commands.get_refinement_service', return_value=mock_rs):
                from src.commands.session_commands import setup_session_commands
                
                mock_bot = MagicMock()
                captured = {}
                
                def mock_command(*args, **kwargs):
                    def decorator(func):
                        captured[kwargs.get('name')] = func
                        return func
                    return decorator
                
                mock_bot.tree.command = mock_command
                setup_session_commands(mock_bot)
                handler = captured.get('startproject')
                
                await handler(mock_interaction, None)
        
        mock_interaction.response.defer.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_detects_existing_session(self, mock_interaction):
        """Test that existing session is detected."""
        existing_session = MagicMock()
        existing_session.get_message_count.return_value = 5
        existing_session.get_word_count.return_value = 50
        
        mock_sm = MagicMock()
        mock_sm.get_session = AsyncMock(return_value=existing_session)
        
        mock_rs = MagicMock()
        mock_rs.is_configured.return_value = False
        
        with patch('src.commands.session_commands.get_session_manager', return_value=mock_sm):
            with patch('src.commands.session_commands.get_refinement_service', return_value=mock_rs):
                from src.commands.session_commands import setup_session_commands
                
                mock_bot = MagicMock()
                captured = {}
                
                def mock_command(*args, **kwargs):
                    def decorator(func):
                        captured[kwargs.get('name')] = func
                        return func
                    return decorator
                
                mock_bot.tree.command = mock_command
                setup_session_commands(mock_bot)
                handler = captured.get('startproject')
                
                await handler(mock_interaction, None)
        
        mock_interaction.followup.send.assert_called_once()
        call_args = str(mock_interaction.followup.send.call_args)
        assert "already have an active session" in call_args


class TestBuildprojectCommand:
    """Tests for the buildproject command."""
    
    @pytest.fixture
    def mock_interaction(self):
        """Create a mock Discord interaction."""
        interaction = AsyncMock()
        interaction.response = AsyncMock()
        interaction.followup = AsyncMock()
        interaction.channel = AsyncMock()
        interaction.user = MagicMock()
        interaction.user.id = 12345
        interaction.user.name = "testuser"
        interaction.channel.id = 67890
        return interaction
    
    @pytest.mark.asyncio
    async def test_no_active_session(self, mock_interaction):
        """Test when no active session exists."""
        mock_sm = MagicMock()
        mock_sm.get_session = AsyncMock(return_value=None)
        
        mock_rs = MagicMock()
        
        with patch('src.commands.session_commands.get_session_manager', return_value=mock_sm):
            with patch('src.commands.session_commands.get_refinement_service', return_value=mock_rs):
                from src.commands.session_commands import setup_session_commands
                
                mock_bot = MagicMock()
                mock_bot.request_semaphore = asyncio.Semaphore(1)
                captured = {}
                
                def mock_command(*args, **kwargs):
                    def decorator(func):
                        captured[kwargs.get('name')] = func
                        return func
                    return decorator
                
                mock_bot.tree.command = mock_command
                setup_session_commands(mock_bot)
                handler = captured.get('buildproject')
                
                await handler(mock_interaction, None)
        
        mock_interaction.response.send_message.assert_called_once()
        call_args = str(mock_interaction.response.send_message.call_args)
        assert "No active prompt session" in call_args
    
    @pytest.mark.asyncio
    async def test_empty_session(self, mock_interaction):
        """Test when session has no messages."""
        mock_session = MagicMock()
        mock_session.get_message_count.return_value = 0
        
        mock_sm = MagicMock()
        mock_sm.get_session = AsyncMock(return_value=mock_session)
        
        mock_rs = MagicMock()
        
        with patch('src.commands.session_commands.get_session_manager', return_value=mock_sm):
            with patch('src.commands.session_commands.get_refinement_service', return_value=mock_rs):
                from src.commands.session_commands import setup_session_commands
                
                mock_bot = MagicMock()
                mock_bot.request_semaphore = asyncio.Semaphore(1)
                captured = {}
                
                def mock_command(*args, **kwargs):
                    def decorator(func):
                        captured[kwargs.get('name')] = func
                        return func
                    return decorator
                
                mock_bot.tree.command = mock_command
                setup_session_commands(mock_bot)
                handler = captured.get('buildproject')
                
                await handler(mock_interaction, None)
        
        mock_interaction.response.send_message.assert_called_once()
        call_args = str(mock_interaction.response.send_message.call_args)
        assert "No messages" in call_args
    
    @pytest.mark.asyncio
    async def test_invalid_model_name(self, mock_interaction):
        """Test with invalid model name."""
        mock_session = MagicMock()
        mock_session.get_message_count.return_value = 5
        
        mock_sm = MagicMock()
        mock_sm.get_session = AsyncMock(return_value=mock_session)
        
        mock_rs = MagicMock()
        
        with patch('src.commands.session_commands.get_session_manager', return_value=mock_sm):
            with patch('src.commands.session_commands.get_refinement_service', return_value=mock_rs):
                from src.commands.session_commands import setup_session_commands
                
                mock_bot = MagicMock()
                mock_bot.request_semaphore = asyncio.Semaphore(1)
                captured = {}
                
                def mock_command(*args, **kwargs):
                    def decorator(func):
                        captured[kwargs.get('name')] = func
                        return func
                    return decorator
                
                mock_bot.tree.command = mock_command
                setup_session_commands(mock_bot)
                handler = captured.get('buildproject')
                
                await handler(mock_interaction, "invalid model!!!")
        
        mock_interaction.response.send_message.assert_called_once()
        call_args = str(mock_interaction.response.send_message.call_args)
        assert "Invalid" in call_args


class TestCancelpromptCommand:
    """Tests for the cancelprompt command."""
    
    @pytest.fixture
    def mock_interaction(self):
        """Create a mock Discord interaction."""
        interaction = AsyncMock()
        interaction.response = AsyncMock()
        interaction.user = MagicMock()
        interaction.user.id = 12345
        interaction.user.name = "testuser"
        interaction.channel = MagicMock()
        interaction.channel.id = 67890
        return interaction
    
    @pytest.mark.asyncio
    async def test_cancel_existing_session(self, mock_interaction):
        """Test cancelling an existing session."""
        cancelled_session = MagicMock()
        cancelled_session.get_message_count.return_value = 5
        cancelled_session.get_word_count.return_value = 50
        
        mock_sm = MagicMock()
        mock_sm.end_session = AsyncMock(return_value=cancelled_session)
        
        mock_rs = MagicMock()
        
        with patch('src.commands.session_commands.get_session_manager', return_value=mock_sm):
            with patch('src.commands.session_commands.get_refinement_service', return_value=mock_rs):
                from src.commands.session_commands import setup_session_commands
                
                mock_bot = MagicMock()
                captured = {}
                
                def mock_command(*args, **kwargs):
                    def decorator(func):
                        captured[kwargs.get('name')] = func
                        return func
                    return decorator
                
                mock_bot.tree.command = mock_command
                setup_session_commands(mock_bot)
                handler = captured.get('cancelprompt')
                
                await handler(mock_interaction)
        
        mock_interaction.response.send_message.assert_called_once()
        call_args = str(mock_interaction.response.send_message.call_args)
        assert "Session Cancelled" in call_args
        assert "5 messages" in call_args
    
    @pytest.mark.asyncio
    async def test_cancel_no_session(self, mock_interaction):
        """Test cancelling when no session exists."""
        mock_sm = MagicMock()
        mock_sm.end_session = AsyncMock(return_value=None)
        
        mock_rs = MagicMock()
        
        with patch('src.commands.session_commands.get_session_manager', return_value=mock_sm):
            with patch('src.commands.session_commands.get_refinement_service', return_value=mock_rs):
                from src.commands.session_commands import setup_session_commands
                
                mock_bot = MagicMock()
                captured = {}
                
                def mock_command(*args, **kwargs):
                    def decorator(func):
                        captured[kwargs.get('name')] = func
                        return func
                    return decorator
                
                mock_bot.tree.command = mock_command
                setup_session_commands(mock_bot)
                handler = captured.get('cancelprompt')
                
                await handler(mock_interaction)
        
        mock_interaction.response.send_message.assert_called_once()
        call_args = str(mock_interaction.response.send_message.call_args)
        assert "No active session" in call_args


class TestSetupMessageListener:
    """Tests for setup_message_listener function."""
    
    def test_returns_callable(self):
        """Test that a callable event handler is returned."""
        from src.commands.session_commands import setup_message_listener
        
        mock_bot = MagicMock()
        mock_bot.event = MagicMock(return_value=lambda f: f)
        
        on_message = setup_message_listener(mock_bot)
        
        assert callable(on_message)
    
    @pytest.mark.asyncio
    async def test_ignores_bot_messages(self):
        """Test that bot messages are ignored."""
        mock_sm = MagicMock()
        mock_sm.get_session = AsyncMock()
        
        mock_rs = MagicMock()
        
        with patch('src.commands.session_commands.get_session_manager', return_value=mock_sm):
            with patch('src.commands.session_commands.get_refinement_service', return_value=mock_rs):
                from src.commands.session_commands import setup_message_listener
                
                mock_bot = MagicMock()
                captured_handler = None
                
                def mock_event(func):
                    nonlocal captured_handler
                    captured_handler = func
                    return func
                
                mock_bot.event = mock_event
                setup_message_listener(mock_bot)
                
                mock_message = MagicMock()
                mock_message.author.bot = True
                
                await captured_handler(mock_message)
        
        mock_sm.get_session.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_ignores_dm_messages(self):
        """Test that DM messages are ignored."""
        mock_sm = MagicMock()
        mock_sm.get_session = AsyncMock()
        
        mock_rs = MagicMock()
        
        with patch('src.commands.session_commands.get_session_manager', return_value=mock_sm):
            with patch('src.commands.session_commands.get_refinement_service', return_value=mock_rs):
                from src.commands.session_commands import setup_message_listener
                
                mock_bot = MagicMock()
                captured_handler = None
                
                def mock_event(func):
                    nonlocal captured_handler
                    captured_handler = func
                    return func
                
                mock_bot.event = mock_event
                setup_message_listener(mock_bot)
                
                mock_message = MagicMock()
                mock_message.author.bot = False
                mock_message.guild = None
                
                await captured_handler(mock_message)
        
        mock_sm.get_session.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_ignores_messages_without_session(self):
        """Test that messages are ignored when no session exists."""
        mock_sm = MagicMock()
        mock_sm.get_session = AsyncMock(return_value=None)
        
        mock_rs = MagicMock()
        
        with patch('src.commands.session_commands.get_session_manager', return_value=mock_sm):
            with patch('src.commands.session_commands.get_refinement_service', return_value=mock_rs):
                from src.commands.session_commands import setup_message_listener
                
                mock_bot = MagicMock()
                captured_handler = None
                
                def mock_event(func):
                    nonlocal captured_handler
                    captured_handler = func
                    return func
                
                mock_bot.event = mock_event
                setup_message_listener(mock_bot)
                
                mock_message = MagicMock()
                mock_message.author.bot = False
                mock_message.guild = MagicMock()
                mock_message.author.id = 12345
                mock_message.channel.id = 67890
                mock_message.content = "Hello"
                
                await captured_handler(mock_message)
        
        mock_sm.get_session.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_ignores_command_messages(self):
        """Test that command messages are ignored."""
        mock_session = MagicMock()
        mock_session.add_message = MagicMock()
        
        mock_sm = MagicMock()
        mock_sm.get_session = AsyncMock(return_value=mock_session)
        
        mock_rs = MagicMock()
        
        with patch('src.commands.session_commands.get_session_manager', return_value=mock_sm):
            with patch('src.commands.session_commands.get_refinement_service', return_value=mock_rs):
                from src.commands.session_commands import setup_message_listener
                
                mock_bot = MagicMock()
                captured_handler = None
                
                def mock_event(func):
                    nonlocal captured_handler
                    captured_handler = func
                    return func
                
                mock_bot.event = mock_event
                setup_message_listener(mock_bot)
                
                mock_message = MagicMock()
                mock_message.author.bot = False
                mock_message.guild = MagicMock()
                mock_message.author.id = 12345
                mock_message.channel.id = 67890
                mock_message.content = "/buildproject"
                
                await captured_handler(mock_message)
        
        mock_session.add_message.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_ignores_empty_messages(self):
        """Test that empty messages are ignored."""
        mock_session = MagicMock()
        mock_session.add_message = MagicMock()
        
        mock_sm = MagicMock()
        mock_sm.get_session = AsyncMock(return_value=mock_session)
        
        mock_rs = MagicMock()
        
        with patch('src.commands.session_commands.get_session_manager', return_value=mock_sm):
            with patch('src.commands.session_commands.get_refinement_service', return_value=mock_rs):
                from src.commands.session_commands import setup_message_listener
                
                mock_bot = MagicMock()
                captured_handler = None
                
                def mock_event(func):
                    nonlocal captured_handler
                    captured_handler = func
                    return func
                
                mock_bot.event = mock_event
                setup_message_listener(mock_bot)
                
                mock_message = MagicMock()
                mock_message.author.bot = False
                mock_message.guild = MagicMock()
                mock_message.author.id = 12345
                mock_message.channel.id = 67890
                mock_message.content = "   "
                
                await captured_handler(mock_message)
        
        mock_session.add_message.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_adds_message_to_session(self):
        """Test that valid messages are added to session."""
        mock_session = MagicMock()
        mock_session.add_message = MagicMock()
        mock_session.add_conversation_turn = MagicMock()
        mock_session.get_word_count.return_value = 10
        mock_session.get_message_count.return_value = 1
        
        mock_sm = MagicMock()
        mock_sm.get_session = AsyncMock(return_value=mock_session)
        
        mock_rs = MagicMock()
        mock_rs.is_configured.return_value = False
        
        with patch('src.commands.session_commands.get_session_manager', return_value=mock_sm):
            with patch('src.commands.session_commands.get_refinement_service', return_value=mock_rs):
                from src.commands.session_commands import setup_message_listener
                
                mock_bot = MagicMock()
                captured_handler = None
                
                def mock_event(func):
                    nonlocal captured_handler
                    captured_handler = func
                    return func
                
                mock_bot.event = mock_event
                setup_message_listener(mock_bot)
                
                mock_message = MagicMock()
                mock_message.author.bot = False
                mock_message.guild = MagicMock()
                mock_message.author.id = 12345
                mock_message.author.name = "testuser"
                mock_message.channel.id = 67890
                mock_message.content = "I want a React app"
                mock_message.id = 111
                mock_message.add_reaction = AsyncMock()
                
                await captured_handler(mock_message)
        
        mock_session.add_message.assert_called_once_with("I want a React app", 111)
        mock_session.add_conversation_turn.assert_called_once_with("user", "I want a React app")


class TestExecuteProjectCreation:
    """Tests for _execute_project_creation function."""
    
    @pytest.fixture
    def mock_interaction(self):
        """Create a mock Discord interaction."""
        interaction = AsyncMock()
        interaction.response = AsyncMock()
        interaction.followup = AsyncMock()
        interaction.channel = AsyncMock()
        interaction.user = MagicMock()
        interaction.user.id = 12345
        interaction.user.name = "testuser"
        interaction.channel.id = 67890
        return interaction
    
    @pytest.mark.asyncio
    async def test_creates_project_with_prompt(self, mock_interaction):
        """Test that project creation is executed."""
        from src.commands.session_commands import _execute_project_creation
        
        mock_bot = MagicMock()
        
        with patch('src.commands.session_commands.create_project_directory') as mock_create:
            with patch('src.commands.session_commands.send_initial_message') as mock_send:
                with patch('src.commands.session_commands.run_copilot_process') as mock_run:
                    with patch('src.commands.session_commands.handle_github_integration') as mock_github:
                        with patch('src.commands.session_commands.update_final_message'):
                            with patch('src.commands.session_commands.CLEANUP_AFTER_PUSH', False):
                                with tempfile.TemporaryDirectory() as tmpdir:
                                    mock_create.return_value = (Path(tmpdir), "test_folder")
                                    mock_send.return_value = AsyncMock()
                                    mock_run.return_value = (False, False, "", MagicMock(returncode=0))
                                    mock_github.return_value = ("", False, "", None)
                                    
                                    await _execute_project_creation(
                                        mock_interaction, "Build a web app", None, mock_bot
                                    )
                                    
                                    mock_create.assert_called_once()
                                    mock_send.assert_called_once()
                                    mock_run.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_handles_directory_creation_failure(self, mock_interaction):
        """Test handling of directory creation failure."""
        from src.commands.session_commands import _execute_project_creation
        
        mock_bot = MagicMock()
        
        with patch('src.commands.session_commands.create_project_directory') as mock_create:
            mock_create.side_effect = OSError("Failed to create directory")
            
            await _execute_project_creation(
                mock_interaction, "Build a web app", None, mock_bot
            )
            
            mock_interaction.channel.send.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_handles_message_send_failure(self, mock_interaction):
        """Test handling of message send failure."""
        from src.commands.session_commands import _execute_project_creation
        
        mock_bot = MagicMock()
        
        with patch('src.commands.session_commands.create_project_directory') as mock_create:
            with patch('src.commands.session_commands.send_initial_message') as mock_send:
                with tempfile.TemporaryDirectory() as tmpdir:
                    mock_create.return_value = (Path(tmpdir), "test_folder")
                    mock_send.side_effect = Exception("Failed to send message")
                    
                    await _execute_project_creation(
                        mock_interaction, "Build a web app", None, mock_bot
                    )
                    
                    assert mock_interaction.channel.send.call_count >= 1
    
    @pytest.mark.asyncio
    async def test_cleanup_on_successful_push(self, mock_interaction):
        """Test cleanup after successful GitHub push."""
        from src.commands.session_commands import _execute_project_creation
        
        mock_bot = MagicMock()
        
        with patch('src.commands.session_commands.create_project_directory') as mock_create:
            with patch('src.commands.session_commands.send_initial_message') as mock_send:
                with patch('src.commands.session_commands.run_copilot_process') as mock_run:
                    with patch('src.commands.session_commands.handle_github_integration') as mock_github:
                        with patch('src.commands.session_commands.update_final_message'):
                            with patch('src.commands.session_commands.cleanup_project_directory') as mock_cleanup:
                                with patch('src.commands.session_commands.CLEANUP_AFTER_PUSH', True):
                                    with tempfile.TemporaryDirectory() as tmpdir:
                                        mock_create.return_value = (Path(tmpdir), "test_folder")
                                        mock_send.return_value = AsyncMock()
                                        mock_run.return_value = (False, False, "", MagicMock(returncode=0))
                                        mock_github.return_value = ("status", True, "desc", "url")
                                        
                                        await _execute_project_creation(
                                            mock_interaction, "Build a web app", None, mock_bot
                                        )
                                        
                                        mock_cleanup.assert_called_once()


class TestStartprojectWithDescription:
    """Tests for startproject with description and AI."""
    
    @pytest.fixture
    def mock_interaction(self):
        """Create a mock Discord interaction."""
        interaction = AsyncMock()
        interaction.response = AsyncMock()
        interaction.followup = AsyncMock()
        interaction.channel = AsyncMock()
        interaction.user = MagicMock()
        interaction.user.id = 12345
        interaction.user.name = "testuser"
        interaction.channel.id = 67890
        return interaction
    
    @pytest.mark.asyncio
    async def test_starts_session_with_description_and_ai(self, mock_interaction):
        """Test starting a session with description and AI refinement."""
        mock_session = MagicMock()
        mock_session.add_message = MagicMock()
        mock_session.add_conversation_turn = MagicMock()
        mock_session.add_bot_message_id = MagicMock()
        
        mock_sm = MagicMock()
        mock_sm.get_session = AsyncMock(return_value=None)
        mock_sm.start_session = AsyncMock(return_value=mock_session)
        
        mock_rs = MagicMock()
        mock_rs.is_configured.return_value = True
        mock_rs.generate_initial_questions = AsyncMock(return_value="What features?")
        
        mock_msg = AsyncMock()
        mock_msg.id = 111
        mock_interaction.followup.send = AsyncMock(return_value=mock_msg)
        mock_interaction.channel.send = AsyncMock(return_value=mock_msg)
        
        with patch('src.commands.session_commands.get_session_manager', return_value=mock_sm):
            with patch('src.commands.session_commands.get_refinement_service', return_value=mock_rs):
                from src.commands.session_commands import setup_session_commands
                
                mock_bot = MagicMock()
                captured = {}
                
                def mock_command(*args, **kwargs):
                    def decorator(func):
                        captured[kwargs.get('name')] = func
                        return func
                    return decorator
                
                mock_bot.tree.command = mock_command
                setup_session_commands(mock_bot)
                handler = captured.get('startproject')
                
                await handler(mock_interaction, "Build a web app")
        
        mock_session.add_message.assert_called_once_with("Build a web app")
        mock_session.add_conversation_turn.assert_called()
    
    @pytest.mark.asyncio
    async def test_starts_session_without_ai(self, mock_interaction):
        """Test starting a session with description but no AI."""
        mock_session = MagicMock()
        mock_session.add_message = MagicMock()
        mock_session.add_conversation_turn = MagicMock()
        mock_session.add_bot_message_id = MagicMock()
        
        mock_sm = MagicMock()
        mock_sm.get_session = AsyncMock(return_value=None)
        mock_sm.start_session = AsyncMock(return_value=mock_session)
        
        mock_rs = MagicMock()
        mock_rs.is_configured.return_value = False
        
        mock_msg = AsyncMock()
        mock_msg.id = 111
        mock_interaction.followup.send = AsyncMock(return_value=mock_msg)
        
        with patch('src.commands.session_commands.get_session_manager', return_value=mock_sm):
            with patch('src.commands.session_commands.get_refinement_service', return_value=mock_rs):
                from src.commands.session_commands import setup_session_commands
                
                mock_bot = MagicMock()
                captured = {}
                
                def mock_command(*args, **kwargs):
                    def decorator(func):
                        captured[kwargs.get('name')] = func
                        return func
                    return decorator
                
                mock_bot.tree.command = mock_command
                setup_session_commands(mock_bot)
                handler = captured.get('startproject')
                
                await handler(mock_interaction, "Build a web app")
        
        call_args = str(mock_interaction.followup.send.call_args)
        assert "AI refinement not configured" in call_args
    
    @pytest.mark.asyncio
    async def test_long_ai_response_splits(self, mock_interaction):
        """Test that long AI responses are split into chunks."""
        mock_session = MagicMock()
        mock_session.add_message = MagicMock()
        mock_session.add_conversation_turn = MagicMock()
        mock_session.add_bot_message_id = MagicMock()
        
        mock_sm = MagicMock()
        mock_sm.get_session = AsyncMock(return_value=None)
        mock_sm.start_session = AsyncMock(return_value=mock_session)
        
        mock_rs = MagicMock()
        mock_rs.is_configured.return_value = True
        
        # Create async generator mock for streaming
        long_response = "Q" * 3000
        async def mock_stream(*args, **kwargs):
            yield (long_response, True, None)
        mock_rs.stream_refinement_response = mock_stream
        
        mock_msg = AsyncMock()
        mock_msg.id = 111
        mock_interaction.followup.send = AsyncMock(return_value=mock_msg)
        mock_interaction.channel.send = AsyncMock(return_value=mock_msg)
        
        with patch('src.commands.session_commands.get_session_manager', return_value=mock_sm):
            with patch('src.commands.session_commands.get_refinement_service', return_value=mock_rs):
                from src.commands.session_commands import setup_session_commands
                
                mock_bot = MagicMock()
                captured = {}
                
                def mock_command(*args, **kwargs):
                    def decorator(func):
                        captured[kwargs.get('name')] = func
                        return func
                    return decorator
                
                mock_bot.tree.command = mock_command
                setup_session_commands(mock_bot)
                handler = captured.get('startproject')
                
                await handler(mock_interaction, "Build a complex app")
        
        # Should have sent multiple messages (header + streaming + potentially file)
        assert mock_interaction.channel.send.call_count >= 1


class TestBuildprojectFullFlow:
    """Tests for buildproject full flow."""
    
    @pytest.fixture
    def mock_interaction(self):
        """Create a mock Discord interaction."""
        interaction = AsyncMock()
        interaction.response = AsyncMock()
        interaction.followup = AsyncMock()
        interaction.channel = AsyncMock()
        interaction.user = MagicMock()
        interaction.user.id = 12345
        interaction.user.name = "testuser"
        interaction.channel.id = 67890
        return interaction
    
    @pytest.mark.asyncio
    async def test_buildproject_with_ai_finalization(self, mock_interaction):
        """Test buildproject with AI prompt finalization."""
        mock_session = MagicMock()
        mock_session.get_message_count.return_value = 5
        mock_session.conversation_history = [{"role": "user", "content": "test"}]
        mock_session.get_full_user_input.return_value = "test prompt"
        mock_session.message_ids = []
        mock_session.refined_prompt = None  # No pre-refined prompt
        
        mock_sm = MagicMock()
        mock_sm.get_session = AsyncMock(return_value=mock_session)
        mock_sm.end_session = AsyncMock()
        
        mock_rs = MagicMock()
        mock_rs.is_configured.return_value = True
        mock_rs.finalize_prompt = AsyncMock(return_value="finalized prompt")
        
        with patch('src.commands.session_commands.get_session_manager', return_value=mock_sm):
            with patch('src.commands.session_commands.get_refinement_service', return_value=mock_rs):
                with patch('src.commands.session_commands._execute_project_creation') as mock_exec:
                    from src.commands.session_commands import setup_session_commands
                    
                    mock_bot = MagicMock()
                    mock_bot.request_semaphore = asyncio.Semaphore(1)
                    captured = {}
                    
                    def mock_command(*args, **kwargs):
                        def decorator(func):
                            captured[kwargs.get('name')] = func
                            return func
                        return decorator
                    
                    mock_bot.tree.command = mock_command
                    setup_session_commands(mock_bot)
                    handler = captured.get('buildproject')
                    
                    await handler(mock_interaction, None)
        
        mock_rs.finalize_prompt.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_buildproject_without_ai(self, mock_interaction):
        """Test buildproject without AI finalization."""
        mock_session = MagicMock()
        mock_session.get_message_count.return_value = 5
        mock_session.conversation_history = []
        mock_session.get_full_user_input.return_value = "raw user input"
        mock_session.message_ids = []
        mock_session.refined_prompt = None  # No pre-refined prompt
        
        mock_sm = MagicMock()
        mock_sm.get_session = AsyncMock(return_value=mock_session)
        mock_sm.end_session = AsyncMock()
        
        mock_rs = MagicMock()
        mock_rs.is_configured.return_value = False
        
        with patch('src.commands.session_commands.get_session_manager', return_value=mock_sm):
            with patch('src.commands.session_commands.get_refinement_service', return_value=mock_rs):
                with patch('src.commands.session_commands._execute_project_creation') as mock_exec:
                    from src.commands.session_commands import setup_session_commands
                    
                    mock_bot = MagicMock()
                    mock_bot.request_semaphore = asyncio.Semaphore(1)
                    captured = {}
                    
                    def mock_command(*args, **kwargs):
                        def decorator(func):
                            captured[kwargs.get('name')] = func
                            return func
                        return decorator
                    
                    mock_bot.tree.command = mock_command
                    setup_session_commands(mock_bot)
                    handler = captured.get('buildproject')
                    
                    await handler(mock_interaction, None)
        
        # Should have used raw user input
        mock_session.get_full_user_input.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_buildproject_prompt_too_long(self, mock_interaction):
        """Test buildproject with prompt that's too long."""
        mock_session = MagicMock()
        mock_session.get_message_count.return_value = 5
        mock_session.conversation_history = []
        mock_session.get_full_user_input.return_value = "x" * 600000  # > MAX_PROMPT_LENGTH
        mock_session.message_ids = []
        mock_session.refined_prompt = None  # No pre-refined prompt
        
        mock_sm = MagicMock()
        mock_sm.get_session = AsyncMock(return_value=mock_session)
        
        mock_rs = MagicMock()
        mock_rs.is_configured.return_value = False
        
        with patch('src.commands.session_commands.get_session_manager', return_value=mock_sm):
            with patch('src.commands.session_commands.get_refinement_service', return_value=mock_rs):
                from src.commands.session_commands import setup_session_commands
                
                mock_bot = MagicMock()
                mock_bot.request_semaphore = asyncio.Semaphore(1)
                captured = {}
                
                def mock_command(*args, **kwargs):
                    def decorator(func):
                        captured[kwargs.get('name')] = func
                        return func
                    return decorator
                
                mock_bot.tree.command = mock_command
                setup_session_commands(mock_bot)
                handler = captured.get('buildproject')
                
                await handler(mock_interaction, None)
        
        call_args = str(mock_interaction.followup.send.call_args)
        assert "Too Long" in call_args
    
    @pytest.mark.asyncio
    async def test_buildproject_message_cleanup(self, mock_interaction):
        """Test that buildproject cleans up session messages."""
        import discord
        
        mock_session = MagicMock()
        mock_session.get_message_count.return_value = 2
        mock_session.conversation_history = []
        mock_session.get_full_user_input.return_value = "test"
        mock_session.message_ids = [111, 222, 333]
        
        mock_sm = MagicMock()
        mock_sm.get_session = AsyncMock(return_value=mock_session)
        mock_sm.end_session = AsyncMock()
        
        mock_rs = MagicMock()
        mock_rs.is_configured.return_value = False
        
        mock_fetched_msg = AsyncMock()
        mock_interaction.channel.fetch_message = AsyncMock(return_value=mock_fetched_msg)
        
        with patch('src.commands.session_commands.get_session_manager', return_value=mock_sm):
            with patch('src.commands.session_commands.get_refinement_service', return_value=mock_rs):
                with patch('src.commands.session_commands._execute_project_creation') as mock_exec:
                    from src.commands.session_commands import setup_session_commands
                    
                    mock_bot = MagicMock()
                    mock_bot.request_semaphore = asyncio.Semaphore(1)
                    captured = {}
                    
                    def mock_command(*args, **kwargs):
                        def decorator(func):
                            captured[kwargs.get('name')] = func
                            return func
                        return decorator
                    
                    mock_bot.tree.command = mock_command
                    setup_session_commands(mock_bot)
                    handler = captured.get('buildproject')
                    
                    await handler(mock_interaction, None)
        
        # Should have tried to delete all 3 messages
        assert mock_interaction.channel.fetch_message.call_count == 3


class TestMessageListenerAIResponse:
    """Tests for message listener AI response handling."""
    
    @pytest.mark.asyncio
    async def test_gets_ai_response_with_refined_prompt(self):
        """Test message listener with AI response containing refined prompt."""
        mock_session = MagicMock()
        mock_session.add_message = MagicMock()
        mock_session.add_conversation_turn = MagicMock()
        mock_session.add_bot_message_id = MagicMock()
        mock_session.get_word_count.return_value = 10
        mock_session.get_message_count.return_value = 1
        mock_session.conversation_history = [{"role": "user", "content": "previous"}]
        
        mock_sm = MagicMock()
        mock_sm.get_session = AsyncMock(return_value=mock_session)
        
        mock_rs = MagicMock()
        mock_rs.is_configured.return_value = True
        
        # Create async generator mock for streaming
        async def mock_stream(*args, **kwargs):
            yield ("Prompt ready!", True, "# Refined prompt content")
        mock_rs.stream_refinement_response = mock_stream
        
        with patch('src.commands.session_commands.get_session_manager', return_value=mock_sm):
            with patch('src.commands.session_commands.get_refinement_service', return_value=mock_rs):
                from src.commands.session_commands import setup_message_listener
                
                mock_bot = MagicMock()
                captured_handler = None
                
                def mock_event(func):
                    nonlocal captured_handler
                    captured_handler = func
                    return func
                
                mock_bot.event = mock_event
                setup_message_listener(mock_bot)
                
                mock_message = AsyncMock()
                mock_message.author.bot = False
                mock_message.guild = MagicMock()
                mock_message.author.id = 12345
                mock_message.author.name = "testuser"
                mock_message.channel.id = 67890
                mock_message.channel = AsyncMock()
                mock_message.channel.typing = MagicMock(return_value=AsyncMock())
                mock_message.content = "Confirmed"
                mock_message.id = 111
                mock_reply = AsyncMock()
                mock_reply.id = 222
                mock_message.reply = AsyncMock(return_value=mock_reply)
                # Need to provide send for initial streaming message
                mock_send_msg = AsyncMock()
                mock_send_msg.id = 333
                mock_message.channel.send = AsyncMock(return_value=mock_send_msg)
                
                await captured_handler(mock_message)
        
        # Should have sent the refined prompt as file via reply
        mock_message.reply.assert_called_once()
        assert mock_session.refined_prompt == "# Refined prompt content"
    
    @pytest.mark.asyncio
    async def test_gets_ai_response_without_refined_prompt(self):
        """Test message listener with AI response but no refined prompt."""
        mock_session = MagicMock()
        mock_session.add_message = MagicMock()
        mock_session.add_conversation_turn = MagicMock()
        mock_session.add_bot_message_id = MagicMock()
        mock_session.get_word_count.return_value = 10
        mock_session.get_message_count.return_value = 1
        mock_session.conversation_history = [{"role": "user", "content": "previous"}]
        
        mock_sm = MagicMock()
        mock_sm.get_session = AsyncMock(return_value=mock_session)
        
        mock_rs = MagicMock()
        mock_rs.is_configured.return_value = True
        
        # Create async generator mock for streaming
        async def mock_stream(*args, **kwargs):
            yield ("What framework do you want?", True, None)
        mock_rs.stream_refinement_response = mock_stream
        
        with patch('src.commands.session_commands.get_session_manager', return_value=mock_sm):
            with patch('src.commands.session_commands.get_refinement_service', return_value=mock_rs):
                from src.commands.session_commands import setup_message_listener
                
                mock_bot = MagicMock()
                captured_handler = None
                
                def mock_event(func):
                    nonlocal captured_handler
                    captured_handler = func
                    return func
                
                mock_bot.event = mock_event
                setup_message_listener(mock_bot)
                
                mock_message = AsyncMock()
                mock_message.author.bot = False
                mock_message.guild = MagicMock()
                mock_message.author.id = 12345
                mock_message.author.name = "testuser"
                mock_message.channel.id = 67890
                mock_message.channel = AsyncMock()
                mock_message.channel.typing = MagicMock(return_value=AsyncMock())
                mock_msg = AsyncMock()
                mock_msg.id = 333
                mock_message.channel.send = AsyncMock(return_value=mock_msg)
                mock_message.content = "More details"
                mock_message.id = 111
                
                await captured_handler(mock_message)
        
        # Should have sent the AI response via streaming (send is called for initial message)
        mock_message.channel.send.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_progress_reminder_every_5_messages(self):
        """Test that progress reminder is shown every 5 messages."""
        mock_session = MagicMock()
        mock_session.add_message = MagicMock()
        mock_session.add_conversation_turn = MagicMock()
        mock_session.add_bot_message_id = MagicMock()
        mock_session.get_word_count.return_value = 100
        mock_session.get_message_count.return_value = 5  # 5th message
        
        mock_sm = MagicMock()
        mock_sm.get_session = AsyncMock(return_value=mock_session)
        
        mock_rs = MagicMock()
        mock_rs.is_configured.return_value = False
        
        with patch('src.commands.session_commands.get_session_manager', return_value=mock_sm):
            with patch('src.commands.session_commands.get_refinement_service', return_value=mock_rs):
                from src.commands.session_commands import setup_message_listener
                
                mock_bot = MagicMock()
                captured_handler = None
                
                def mock_event(func):
                    nonlocal captured_handler
                    captured_handler = func
                    return func
                
                mock_bot.event = mock_event
                setup_message_listener(mock_bot)
                
                mock_message = MagicMock()
                mock_message.author.bot = False
                mock_message.guild = MagicMock()
                mock_message.author.id = 12345
                mock_message.author.name = "testuser"
                mock_message.channel.id = 67890
                mock_message.content = "More info"
                mock_message.id = 111
                mock_message.add_reaction = AsyncMock()
                mock_msg = AsyncMock()
                mock_msg.id = 222
                mock_message.channel.send = AsyncMock(return_value=mock_msg)
                
                await captured_handler(mock_message)
        
        # Should show progress reminder
        mock_message.channel.send.assert_called_once()
        call_args = str(mock_message.channel.send.call_args)
        assert "Session progress" in call_args
