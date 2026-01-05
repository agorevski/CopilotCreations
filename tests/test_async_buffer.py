"""
Tests for async_buffer module.

This module tests the AsyncOutputBuffer class which provides thread-safe
buffering for async output streaming operations.
"""

import asyncio
import pytest

from src.utils.async_buffer import AsyncOutputBuffer


class TestAsyncOutputBuffer:
    """Tests for AsyncOutputBuffer class covering core operations and thread safety."""
    
    @pytest.mark.asyncio
    async def test_async_operations(self):
        """Tests async append/get operations.

        Verifies:
            - Basic append and content retrieval
            - Getting buffer as list with correct ordering
            - List returns a copy (not the original) to prevent mutation
            - Empty buffer returns empty string/list
        """
        buffer = AsyncOutputBuffer()
        
        # Test empty buffer first
        assert await buffer.get_content() == ""
        assert await buffer.get_list() == []
        
        # Test append and content retrieval
        await buffer.append("Hello ")
        await buffer.append("World!")
        assert await buffer.get_content() == "Hello World!"
        
        # Test get_list returns ordered items
        buffer2 = AsyncOutputBuffer()
        await buffer2.append("Line 1\n")
        await buffer2.append("Line 2\n")
        items = await buffer2.get_list()
        assert items == ["Line 1\n", "Line 2\n"]
        
        # Verify get_list returns a copy
        items.append("Item 3")
        original = await buffer2.get_list()
        assert len(original) == 2  # Original unchanged
    
    @pytest.mark.asyncio
    async def test_concurrent_appends(self):
        """Verifies thread safety with concurrent append operations.

        Runs 3 concurrent tasks each appending 10 items. All 30 items
        from the concurrent tasks should be captured in the buffer.
        """
        buffer = AsyncOutputBuffer()
        
        async def append_items(prefix: str, count: int):
            """Appends multiple items to the buffer with a prefix.

            Args:
                prefix: String prefix for each item.
                count: Number of items to append.
            """
            for i in range(count):
                await buffer.append(f"{prefix}{i}")
        
        await asyncio.gather(
            append_items("A", 10),
            append_items("B", 10),
            append_items("C", 10)
        )
        
        items = await buffer.get_list()
        assert len(items) == 30
    
    def test_sync_operations(self):
        """Tests synchronous append/get operations.

        Verifies:
            - Basic sync append and content retrieval
            - Sync get_content returns concatenated buffer
        """
        buffer = AsyncOutputBuffer()
        
        buffer.append_sync("Hello ")
        buffer.append_sync("World!")
        assert buffer.get_content_sync() == "Hello World!"
        
        # Test separate buffer for get_content
        buffer2 = AsyncOutputBuffer()
        buffer2.append_sync("Test content")
        assert buffer2.get_content_sync() == "Test content"
    
    @pytest.mark.asyncio
    async def test_mixed_sync_async(self):
        """Tests interoperability between sync and async operations.

        Verifies that both sync and async appends work together seamlessly
        and produce the expected combined output.
        """
        buffer = AsyncOutputBuffer()
        
        buffer.append_sync("Sync ")
        await buffer.append("Async")
        
        content = await buffer.get_content()
        assert content == "Sync Async"
