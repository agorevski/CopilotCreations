"""
Tests for session manager functionality.
"""

import asyncio
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

import pytest

from src.utils.session_manager import (
    PromptSession,
    SessionManager,
    get_session_manager,
    reset_session_manager,
)


class TestPromptSession:
    """Tests for PromptSession dataclass."""
    
    def test_create_session(self):
        """Test creating a new session."""
        session = PromptSession(user_id=123, channel_id=456)
        
        assert session.user_id == 123
        assert session.channel_id == 456
        assert session.messages == []
        assert session.conversation_history == []
        assert session.refined_prompt is None
        assert session.model is None
    
    def test_add_message(self):
        """Test adding messages to session."""
        session = PromptSession(user_id=123, channel_id=456)
        
        session.add_message("Hello")
        session.add_message("World")
        
        assert len(session.messages) == 2
        assert session.messages[0] == "Hello"
        assert session.messages[1] == "World"
    
    def test_add_conversation_turn(self):
        """Test adding conversation turns."""
        session = PromptSession(user_id=123, channel_id=456)
        
        session.add_conversation_turn("user", "Hello")
        session.add_conversation_turn("assistant", "Hi there!")
        
        assert len(session.conversation_history) == 2
        assert session.conversation_history[0] == {"role": "user", "content": "Hello"}
        assert session.conversation_history[1] == {"role": "assistant", "content": "Hi there!"}
    
    def test_get_full_user_input(self):
        """Test getting concatenated user input."""
        session = PromptSession(user_id=123, channel_id=456)
        
        session.add_message("First message")
        session.add_message("Second message")
        
        full_input = session.get_full_user_input()
        assert full_input == "First message\n\nSecond message"
    
    def test_get_word_count(self):
        """Test word counting."""
        session = PromptSession(user_id=123, channel_id=456)
        
        session.add_message("Hello world")
        session.add_message("This is a test")
        
        assert session.get_word_count() == 6
    
    def test_get_char_count(self):
        """Test character counting."""
        session = PromptSession(user_id=123, channel_id=456)
        
        session.add_message("Hello")  # 5 chars
        session.add_message("World")  # 5 chars + 2 newlines between
        
        assert session.get_char_count() == 12  # "Hello\n\nWorld"
    
    def test_get_message_count(self):
        """Test message counting."""
        session = PromptSession(user_id=123, channel_id=456)
        
        session.add_message("One")
        session.add_message("Two")
        session.add_message("Three")
        
        assert session.get_message_count() == 3
    
    def test_is_expired(self):
        """Test session expiration check."""
        session = PromptSession(user_id=123, channel_id=456)
        
        # Should not be expired immediately
        assert not session.is_expired(30)
        
        # Manually set last_activity to the past
        session.last_activity = datetime.now() - timedelta(minutes=31)
        assert session.is_expired(30)
    
    def test_get_final_prompt_without_refinement(self):
        """Test getting final prompt when no refinement exists."""
        session = PromptSession(user_id=123, channel_id=456)
        
        session.add_message("Build me a web app")
        
        assert session.get_final_prompt() == "Build me a web app"
    
    def test_get_final_prompt_with_refinement(self):
        """Test getting final prompt when refinement exists."""
        session = PromptSession(user_id=123, channel_id=456)
        
        session.add_message("Build me a web app")
        session.refined_prompt = "A comprehensive web application with React and Node.js"
        
        assert session.get_final_prompt() == "A comprehensive web application with React and Node.js"


class TestSessionManager:
    """Tests for SessionManager class."""
    
    @pytest.fixture
    def manager(self):
        """Create a fresh session manager for each test."""
        return SessionManager(timeout_minutes=30)
    
    @pytest.mark.asyncio
    async def test_start_session(self, manager):
        """Test starting a new session."""
        session = await manager.start_session(123, 456)
        
        assert session is not None
        assert session.user_id == 123
        assert session.channel_id == 456
    
    @pytest.mark.asyncio
    async def test_get_session(self, manager):
        """Test retrieving an existing session."""
        await manager.start_session(123, 456)
        
        session = await manager.get_session(123, 456)
        
        assert session is not None
        assert session.user_id == 123
    
    @pytest.mark.asyncio
    async def test_get_session_not_found(self, manager):
        """Test retrieving non-existent session."""
        session = await manager.get_session(999, 999)
        
        assert session is None
    
    @pytest.mark.asyncio
    async def test_get_session_expired(self, manager):
        """Test that expired sessions return None."""
        session = await manager.start_session(123, 456)
        session.last_activity = datetime.now() - timedelta(minutes=31)
        
        result = await manager.get_session(123, 456)
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_end_session(self, manager):
        """Test ending a session."""
        await manager.start_session(123, 456)
        
        session = await manager.end_session(123, 456)
        
        assert session is not None
        assert await manager.get_session(123, 456) is None
    
    @pytest.mark.asyncio
    async def test_end_session_not_found(self, manager):
        """Test ending non-existent session."""
        session = await manager.end_session(999, 999)
        
        assert session is None
    
    @pytest.mark.asyncio
    async def test_has_active_session(self, manager):
        """Test checking for active session."""
        assert not await manager.has_active_session(123, 456)
        
        await manager.start_session(123, 456)
        
        assert await manager.has_active_session(123, 456)
    
    @pytest.mark.asyncio
    async def test_add_message(self, manager):
        """Test adding message to session."""
        await manager.start_session(123, 456)
        
        result = await manager.add_message(123, 456, "Hello")
        
        assert result is True
        session = await manager.get_session(123, 456)
        assert "Hello" in session.messages
    
    @pytest.mark.asyncio
    async def test_add_message_no_session(self, manager):
        """Test adding message without active session."""
        result = await manager.add_message(123, 456, "Hello")
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_cleanup_expired_sessions(self, manager):
        """Test cleaning up expired sessions."""
        session1 = await manager.start_session(123, 456)
        session2 = await manager.start_session(789, 101)
        
        # Expire one session
        session1.last_activity = datetime.now() - timedelta(minutes=31)
        
        count = await manager.cleanup_expired_sessions()
        
        assert count == 1
        assert await manager.get_session(123, 456) is None
        assert await manager.get_session(789, 101) is not None
    
    def test_get_active_session_count(self, manager):
        """Test getting active session count."""
        assert manager.get_active_session_count() == 0
    
    @pytest.mark.asyncio
    async def test_start_session_replaces_existing(self, manager):
        """Test that starting a new session replaces existing one."""
        session1 = await manager.start_session(123, 456)
        session1.add_message("Old message")
        
        session2 = await manager.start_session(123, 456)
        
        assert session2.get_message_count() == 0
    
    @pytest.mark.asyncio
    async def test_cleanup_expired_sessions_logs_when_cleaned(self, manager):
        """Test that cleanup logs when sessions are cleaned."""
        session1 = await manager.start_session(123, 456)
        session1.last_activity = datetime.now() - timedelta(minutes=31)
        
        with patch('src.utils.session_manager.logger') as mock_logger:
            count = await manager.cleanup_expired_sessions()
            
            assert count == 1
            mock_logger.info.assert_called()
    
    @pytest.mark.asyncio
    async def test_start_cleanup_task(self, manager):
        """Test starting the cleanup task."""
        with patch('asyncio.create_task') as mock_create_task:
            mock_task = MagicMock()
            mock_task.done.return_value = True
            mock_create_task.return_value = mock_task
            
            await manager.start_cleanup_task(interval_minutes=1)
            
            mock_create_task.assert_called_once()
    
    def test_stop_cleanup_task(self, manager):
        """Test stopping the cleanup task."""
        mock_task = MagicMock()
        mock_task.done.return_value = False
        manager._cleanup_task = mock_task
        
        manager.stop_cleanup_task()
        
        mock_task.cancel.assert_called_once()
    
    def test_stop_cleanup_task_not_running(self, manager):
        """Test stopping cleanup task when not running."""
        manager._cleanup_task = None
        
        # Should not raise any exception
        manager.stop_cleanup_task()


class TestSingletonSessionManager:
    """Tests for singleton session manager access."""
    
    def setup_method(self):
        """Reset the singleton before each test."""
        reset_session_manager()
    
    def teardown_method(self):
        """Reset the singleton after each test."""
        reset_session_manager()
    
    def test_get_session_manager_returns_same_instance(self):
        """Test that get_session_manager returns the same instance."""
        manager1 = get_session_manager()
        manager2 = get_session_manager()
        
        assert manager1 is manager2
    
    def test_reset_session_manager(self):
        """Test that reset clears the singleton."""
        manager1 = get_session_manager()
        reset_session_manager()
        manager2 = get_session_manager()
        
        assert manager1 is not manager2
