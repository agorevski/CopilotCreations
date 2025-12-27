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
        self._buffer: List[str] = []
        self._lock = asyncio.Lock()
    
    async def append(self, item: str) -> None:
        """Append an item to the buffer atomically."""
        async with self._lock:
            self._buffer.append(item)
    
    async def get_content(self) -> str:
        """Get all buffer content as a joined string."""
        async with self._lock:
            return ''.join(self._buffer)
    
    async def get_list(self) -> List[str]:
        """Get a copy of the buffer as a list."""
        async with self._lock:
            return self._buffer.copy()
    
    def append_sync(self, item: str) -> None:
        """Synchronous append for use in sync contexts.
        
        Note: Use this only when you're certain there are no concurrent
        async operations. Prefer the async append() method.
        """
        self._buffer.append(item)
    
    def get_content_sync(self) -> str:
        """Synchronous get for use in sync contexts.
        
        Note: Use this only when you're certain there are no concurrent
        async operations. Prefer the async get_content() method.
        """
        return ''.join(self._buffer)
