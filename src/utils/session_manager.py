"""
Session manager for tracking user prompt-building sessions.

This module provides functionality to track and manage user sessions
where they build prompts across multiple messages before project creation.
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from .logging import logger


@dataclass
class PromptSession:
    """Represents an active prompt-building session for a user."""
    
    user_id: int
    channel_id: int
    started_at: datetime = field(default_factory=datetime.now)
    last_activity: datetime = field(default_factory=datetime.now)
    messages: List[str] = field(default_factory=list)
    conversation_history: List[Dict[str, str]] = field(default_factory=list)
    refined_prompt: Optional[str] = None
    model: Optional[str] = None
    message_ids: List[int] = field(default_factory=list)  # Discord message IDs to delete on build
    
    def add_message(self, content: str, message_id: Optional[int] = None) -> None:
        """Add a user message to the session.
        
        Args:
            content: The message content to add.
            message_id: Optional Discord message ID to track for deletion.
        """
        self.messages.append(content)
        if message_id:
            self.message_ids.append(message_id)
        self.last_activity = datetime.now()
    
    def add_bot_message_id(self, message_id: int) -> None:
        """Track a bot message ID for deletion on build.
        
        Args:
            message_id: Discord message ID to track.
        """
        self.message_ids.append(message_id)
    
    def add_conversation_turn(self, role: str, content: str) -> None:
        """Add a conversation turn (user or assistant) to history.
        
        Args:
            role: The role of the speaker ('user' or 'assistant').
            content: The message content.
        """
        self.conversation_history.append({"role": role, "content": content})
        self.last_activity = datetime.now()
    
    def get_full_user_input(self) -> str:
        """Get all user messages concatenated.
        
        Returns:
            All user messages joined with double newlines.
        """
        return "\n\n".join(self.messages)
    
    def get_word_count(self) -> int:
        """Get total word count across all messages.
        
        Returns:
            Total number of words in all messages.
        """
        full_text = self.get_full_user_input()
        return len(full_text.split())
    
    def get_char_count(self) -> int:
        """Get total character count across all messages.
        
        Returns:
            Total number of characters in all messages.
        """
        return len(self.get_full_user_input())
    
    def get_message_count(self) -> int:
        """Get total number of messages.
        
        Returns:
            Number of messages in the session.
        """
        return len(self.messages)
    
    def is_expired(self, timeout_minutes: int) -> bool:
        """Check if the session has expired due to inactivity.
        
        Args:
            timeout_minutes: Number of minutes of inactivity before expiration.
            
        Returns:
            True if the session has expired, False otherwise.
        """
        expiry_time = self.last_activity + timedelta(minutes=timeout_minutes)
        return datetime.now() > expiry_time
    
    def get_final_prompt(self) -> str:
        """Get the final prompt to use for project creation.
        
        Returns the refined prompt if available, otherwise the raw user input.
        """
        return self.refined_prompt if self.refined_prompt else self.get_full_user_input()


class SessionManager:
    """Manages prompt-building sessions for users."""
    
    def __init__(self, timeout_minutes: int = 30):
        """Initialize the session manager.
        
        Args:
            timeout_minutes: Session timeout in minutes (default 30).
        """
        self.timeout_minutes = timeout_minutes
        self._sessions: Dict[Tuple[int, int], PromptSession] = {}
        self._lock = asyncio.Lock()
        self._cleanup_task: Optional[asyncio.Task] = None
    
    def _get_key(self, user_id: int, channel_id: int) -> Tuple[int, int]:
        """Get the session key for a user/channel pair.
        
        Args:
            user_id: Discord user ID.
            channel_id: Discord channel ID.
            
        Returns:
            A tuple of (user_id, channel_id) to use as dictionary key.
        """
        return (user_id, channel_id)
    
    async def start_session(self, user_id: int, channel_id: int) -> PromptSession:
        """Start a new prompt-building session for a user.
        
        Args:
            user_id: Discord user ID.
            channel_id: Discord channel ID.
            
        Returns:
            The newly created session.
        """
        async with self._lock:
            key = self._get_key(user_id, channel_id)
            
            # End any existing session
            if key in self._sessions:
                logger.info(f"Ending existing session for user {user_id} in channel {channel_id}")
            
            session = PromptSession(user_id=user_id, channel_id=channel_id)
            self._sessions[key] = session
            logger.info(f"Started new session for user {user_id} in channel {channel_id}")
            
            return session
    
    async def get_session(self, user_id: int, channel_id: int) -> Optional[PromptSession]:
        """Get an active session for a user.
        
        Args:
            user_id: Discord user ID.
            channel_id: Discord channel ID.
            
        Returns:
            The session if it exists and is not expired, None otherwise.
        """
        async with self._lock:
            key = self._get_key(user_id, channel_id)
            session = self._sessions.get(key)
            
            if session is None:
                return None
            
            if session.is_expired(self.timeout_minutes):
                logger.info(f"Session expired for user {user_id} in channel {channel_id}")
                del self._sessions[key]
                return None
            
            return session
    
    async def end_session(self, user_id: int, channel_id: int) -> Optional[PromptSession]:
        """End and remove a session.
        
        Args:
            user_id: Discord user ID.
            channel_id: Discord channel ID.
            
        Returns:
            The ended session if it existed, None otherwise.
        """
        async with self._lock:
            key = self._get_key(user_id, channel_id)
            session = self._sessions.pop(key, None)
            
            if session:
                logger.info(f"Ended session for user {user_id} in channel {channel_id}")
            
            return session
    
    async def has_active_session(self, user_id: int, channel_id: int) -> bool:
        """Check if a user has an active session in a channel.
        
        Args:
            user_id: Discord user ID.
            channel_id: Discord channel ID.
            
        Returns:
            True if an active session exists, False otherwise.
        """
        session = await self.get_session(user_id, channel_id)
        return session is not None
    
    async def add_message(self, user_id: int, channel_id: int, content: str) -> bool:
        """Add a message to an active session.
        
        Args:
            user_id: Discord user ID.
            channel_id: Discord channel ID.
            content: Message content to add.
            
        Returns:
            True if message was added, False if no active session.
        """
        session = await self.get_session(user_id, channel_id)
        if session:
            session.add_message(content)
            return True
        return False
    
    async def cleanup_expired_sessions(self) -> int:
        """Remove all expired sessions.
        
        Returns:
            Number of sessions removed.
        """
        async with self._lock:
            expired_keys = [
                key for key, session in self._sessions.items()
                if session.is_expired(self.timeout_minutes)
            ]
            
            for key in expired_keys:
                del self._sessions[key]
            
            if expired_keys:
                logger.info(f"Cleaned up {len(expired_keys)} expired sessions")
            
            return len(expired_keys)
    
    async def start_cleanup_task(self, interval_minutes: int = 5) -> None:
        """Start a background task to periodically clean up expired sessions.
        
        Args:
            interval_minutes: How often to run cleanup (default 5 minutes).
        """
        async def cleanup_loop():
            while True:
                await asyncio.sleep(interval_minutes * 60)
                await self.cleanup_expired_sessions()
        
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(cleanup_loop())
            logger.info(f"Started session cleanup task (interval: {interval_minutes} minutes)")
    
    def stop_cleanup_task(self) -> None:
        """Stop the background cleanup task.
        
        Cancels the periodic cleanup task if it is running.
        """
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            logger.info("Stopped session cleanup task")
    
    def get_active_session_count(self) -> int:
        """Get the number of active sessions.
        
        Returns:
            Count of currently active sessions.
        """
        return len(self._sessions)


# Singleton instance for easy access
_session_manager: Optional[SessionManager] = None


def get_session_manager(timeout_minutes: int = 30) -> SessionManager:
    """Get the singleton session manager instance.
    
    Args:
        timeout_minutes: Session timeout (only used on first call).
        
    Returns:
        The session manager instance.
    """
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager(timeout_minutes=timeout_minutes)
    return _session_manager


def reset_session_manager() -> None:
    """Reset the session manager (useful for testing).
    
    Stops any running cleanup task and clears the singleton instance.
    """
    global _session_manager
    if _session_manager:
        _session_manager.stop_cleanup_task()
    _session_manager = None
