"""
Tests for async_buffer module.
"""

import asyncio
import pytest

from src.utils.async_buffer import AsyncOutputBuffer


class TestAsyncOutputBuffer:
    """Tests for AsyncOutputBuffer class."""
    
    @pytest.mark.asyncio
    async def test_append_and_get_content(self):
        """Test basic append and get content operations."""
        buffer = AsyncOutputBuffer()
        
        await buffer.append("Hello ")
        await buffer.append("World!")
        
        content = await buffer.get_content()
        assert content == "Hello World!"
    
    @pytest.mark.asyncio
    async def test_get_list(self):
        """Test getting buffer as list."""
        buffer = AsyncOutputBuffer()
        
        await buffer.append("Line 1\n")
        await buffer.append("Line 2\n")
        
        items = await buffer.get_list()
        assert len(items) == 2
        assert items[0] == "Line 1\n"
        assert items[1] == "Line 2\n"
    
    @pytest.mark.asyncio
    async def test_get_list_returns_copy(self):
        """Test that get_list returns a copy, not the original."""
        buffer = AsyncOutputBuffer()
        
        await buffer.append("Item 1")
        items = await buffer.get_list()
        
        # Modifying the returned list should not affect the buffer
        items.append("Item 2")
        
        original = await buffer.get_list()
        assert len(original) == 1
    
    @pytest.mark.asyncio
    async def test_empty_buffer(self):
        """Test empty buffer returns empty string."""
        buffer = AsyncOutputBuffer()
        
        content = await buffer.get_content()
        assert content == ""
        
        items = await buffer.get_list()
        assert items == []
    
    @pytest.mark.asyncio
    async def test_concurrent_appends(self):
        """Test that concurrent appends are handled safely."""
        buffer = AsyncOutputBuffer()
        
        async def append_items(prefix: str, count: int):
            for i in range(count):
                await buffer.append(f"{prefix}{i}")
        
        # Run multiple concurrent append tasks
        await asyncio.gather(
            append_items("A", 10),
            append_items("B", 10),
            append_items("C", 10)
        )
        
        items = await buffer.get_list()
        assert len(items) == 30
    
    def test_sync_append(self):
        """Test synchronous append method."""
        buffer = AsyncOutputBuffer()
        
        buffer.append_sync("Hello ")
        buffer.append_sync("World!")
        
        content = buffer.get_content_sync()
        assert content == "Hello World!"
    
    def test_sync_get_content(self):
        """Test synchronous get content method."""
        buffer = AsyncOutputBuffer()
        
        buffer.append_sync("Test content")
        
        content = buffer.get_content_sync()
        assert content == "Test content"
    
    @pytest.mark.asyncio
    async def test_mixed_sync_async(self):
        """Test mixing sync and async operations."""
        buffer = AsyncOutputBuffer()
        
        buffer.append_sync("Sync ")
        await buffer.append("Async")
        
        content = await buffer.get_content()
        assert content == "Sync Async"
