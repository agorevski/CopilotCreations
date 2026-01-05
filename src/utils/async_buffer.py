"""
Thread-safe async output buffer for concurrent operations.
"""

import asyncio
from typing import List


class AsyncOutputBuffer:
    """Thread-safe output buffer for async operations.
    
    Provides atomic append and get operations using an asyncio lock
    to prevent race conditions when multiple async tasks access the buffer.
    """
    
    def __init__(self) -> None:
        """Initialize the async output buffer.
        
        Creates an empty buffer with an asyncio lock for thread-safe
        concurrent access.
        """
        self._buffer: List[str] = []
        self._lock = asyncio.Lock()
    
    async def append(self, item: str) -> None:
        """Append an item to the buffer atomically.
        
        Args:
            item: The string item to append to the buffer.
        """
        async with self._lock:
            self._buffer.append(item)
    
    async def get_content(self) -> str:
        """Get all buffer content as a joined string.
        
        Returns:
            A single string containing all buffer items concatenated together.
        """
        async with self._lock:
            return ''.join(self._buffer)
    
    async def get_list(self) -> List[str]:
        """Get a copy of the buffer as a list.
        
        Returns:
            A shallow copy of the internal buffer list.
        """
        async with self._lock:
            return self._buffer.copy()
    
    def append_sync(self, item: str) -> None:
        """Synchronous append for use in sync contexts.
        
        Args:
            item: The string item to append to the buffer.
            
        Note:
            Use this only when you're certain there are no concurrent
            async operations. Prefer the async append() method.
        """
        self._buffer.append(item)
    
    def get_content_sync(self) -> str:
        """Synchronous get for use in sync contexts.
        
        Returns:
            A single string containing all buffer items concatenated together.
            
        Note:
            Use this only when you're certain there are no concurrent
            async operations. Prefer the async get_content() method.
        """
        return ''.join(self._buffer)
