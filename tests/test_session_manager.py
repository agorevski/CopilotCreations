"""
Tests for session manager functionality.

This module tests the PromptSession dataclass and SessionManager class
which handle user prompt sessions for project creation.
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
    """Tests for PromptSession dataclass covering all session operations."""
    
    def test_session_basics(self):
        """
        Tests basic session operations:
        - Creation with user/channel IDs
        - Empty initial state
        - Adding messages
        - Adding conversation turns
        - Getting full user input (concatenated)
        - Word and character counting
        - Message counting
        """
        # Creation and initial state
        session = PromptSession(user_id=123, channel_id=456)
        assert session.user_id == 123
        assert session.channel_id == 456
        assert session.messages == []
        assert session.conversation_history == []
        assert session.refined_prompt is None
        assert session.model is None
        
        # Adding messages
        session.add_message("Hello")
        session.add_message("World")
        assert len(session.messages) == 2
        assert session.messages == ["Hello", "World"]
        
        # Adding conversation turns
        session.add_conversation_turn("user", "Hello")
        session.add_conversation_turn("assistant", "Hi there!")
        assert len(session.conversation_history) == 2
        assert session.conversation_history[0] == {"role": "user", "content": "Hello"}
        assert session.conversation_history[1] == {"role": "assistant", "content": "Hi there!"}
        
        # Full user input (concatenated with double newlines)
        session2 = PromptSession(user_id=1, channel_id=1)
        session2.add_message("First message")
        session2.add_message("Second message")
        assert session2.get_full_user_input() == "First message\n\nSecond message"
        
        # Word count
        session3 = PromptSession(user_id=1, channel_id=1)
        session3.add_message("Hello world")
        session3.add_message("This is a test")
        assert session3.get_word_count() == 6
        
        # Character count (includes newlines between messages)
        session4 = PromptSession(user_id=1, channel_id=1)
        session4.add_message("Hello")  # 5 chars
        session4.add_message("World")  # 5 chars + 2 newlines = 12 total
        assert session4.get_char_count() == 12
        
        # Message count
        session5 = PromptSession(user_id=1, channel_id=1)
        session5.add_message("One")
        session5.add_message("Two")
        session5.add_message("Three")
        assert session5.get_message_count() == 3
    
    def test_session_expiration(self):
        """
        Tests session expiration checking:
        - Fresh session not expired
        - Session expired after timeout
        """
        session = PromptSession(user_id=123, channel_id=456)
        
        # Fresh session not expired
        assert not session.is_expired(30)
        
        # Expired session
        session.last_activity = datetime.now() - timedelta(minutes=31)
        assert session.is_expired(30)
    
    def test_final_prompt(self):
        """
        Tests get_final_prompt behavior:
        - Without refinement (returns raw user input)
        - With refinement (returns refined prompt)
        """
        # Without refinement
        session = PromptSession(user_id=123, channel_id=456)
        session.add_message("Build me a web app")
        assert session.get_final_prompt() == "Build me a web app"
        
        # With refinement
        session.refined_prompt = "A comprehensive web application with React and Node.js"
        assert session.get_final_prompt() == "A comprehensive web application with React and Node.js"


class TestSessionManager:
    """Tests for SessionManager class covering CRUD operations and cleanup."""
    
    @pytest.fixture
    def manager(self):
        """Create a fresh session manager for each test."""
        return SessionManager(timeout_minutes=30)
    
    @pytest.mark.asyncio
    async def test_session_crud(self, manager):
        """
        Tests session CRUD operations:
        - Start session
        - Get existing session
        - Get non-existent session (None)
        - Get expired session (None)
        - End session
        - End non-existent session (None)
        - has_active_session check
        - Add message to session
        - Add message without session (False)
        - Start session replaces existing
        """
        # Start session
        session = await manager.start_session(123, 456)
        assert session is not None
        assert session.user_id == 123
        assert session.channel_id == 456
        
        # Get existing session
        found = await manager.get_session(123, 456)
        assert found is not None
        assert found.user_id == 123
        
        # Get non-existent session
        assert await manager.get_session(999, 999) is None
        
        # Get expired session returns None
        session.last_activity = datetime.now() - timedelta(minutes=31)
        assert await manager.get_session(123, 456) is None
        
        # End session (create new one first)
        await manager.start_session(123, 456)
        ended = await manager.end_session(123, 456)
        assert ended is not None
        assert await manager.get_session(123, 456) is None
        
        # End non-existent session
        assert await manager.end_session(999, 999) is None
        
        # has_active_session
        assert not await manager.has_active_session(123, 456)
        await manager.start_session(123, 456)
        assert await manager.has_active_session(123, 456)
        
        # Add message to session
        result = await manager.add_message(123, 456, "Hello")
        assert result is True
        session = await manager.get_session(123, 456)
        assert "Hello" in session.messages
        
        # Add message without session
        await manager.end_session(123, 456)
        assert await manager.add_message(123, 456, "Hello") is False
        
        # Start session replaces existing
        s1 = await manager.start_session(123, 456)
        s1.add_message("Old message")
        s2 = await manager.start_session(123, 456)
        assert s2.get_message_count() == 0
    
    @pytest.mark.asyncio
    async def test_cleanup_operations(self, manager):
        """
        Tests cleanup operations:
        - Cleanup expired sessions
        - get_active_session_count
        - Cleanup logs when sessions cleaned
        - Start/stop cleanup task
        """
        # Cleanup expired sessions
        session1 = await manager.start_session(123, 456)
        session2 = await manager.start_session(789, 101)
        session1.last_activity = datetime.now() - timedelta(minutes=31)  # Expire one
        
        count = await manager.cleanup_expired_sessions()
        assert count == 1
        assert await manager.get_session(123, 456) is None
        assert await manager.get_session(789, 101) is not None
        
        # get_active_session_count starts at 0 for fresh manager
        fresh_manager = SessionManager(timeout_minutes=30)
        assert fresh_manager.get_active_session_count() == 0
        
        # Cleanup logs when sessions cleaned
        manager2 = SessionManager(timeout_minutes=30)
        s = await manager2.start_session(123, 456)
        s.last_activity = datetime.now() - timedelta(minutes=31)
        
        with patch('src.utils.session_manager.logger') as mock_logger:
            await manager2.cleanup_expired_sessions()
            mock_logger.info.assert_called()
        
        # Start cleanup task
        with patch('asyncio.create_task') as mock_create:
            mock_task = MagicMock()
            mock_task.done.return_value = True
            mock_create.return_value = mock_task
            await manager.start_cleanup_task(interval_minutes=1)
            mock_create.assert_called_once()
        
        # Stop cleanup task
        mock_task = MagicMock()
        mock_task.done.return_value = False
        manager._cleanup_task = mock_task
        manager.stop_cleanup_task()
        mock_task.cancel.assert_called_once()
        
        # Stop cleanup task when not running
        manager._cleanup_task = None
        manager.stop_cleanup_task()  # Should not raise


class TestSingletonSessionManager:
    """Tests for singleton session manager access."""
    
    def setup_method(self):
        """Reset the singleton before each test."""
        reset_session_manager()
    
    def teardown_method(self):
        """Reset the singleton after each test."""
        reset_session_manager()
    
    def test_singleton_behavior(self):
        """
        Tests singleton behavior:
        - get_session_manager returns same instance
        - reset_session_manager clears singleton
        """
        manager1 = get_session_manager()
        manager2 = get_session_manager()
        assert manager1 is manager2
        
        reset_session_manager()
        manager3 = get_session_manager()
        assert manager1 is not manager3
