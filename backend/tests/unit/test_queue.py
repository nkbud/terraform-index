"""Tests for queue implementations."""

import pytest
import asyncio

from indexer.queue.memory import MemoryQueue


@pytest.mark.asyncio
async def test_memory_queue_basic_operations():
    """Test basic queue operations."""
    queue = MemoryQueue(maxsize=5)
    await queue.start()
    
    # Test empty queue
    assert await queue.empty() is True
    assert await queue.qsize() == 0
    
    # Test put and get
    test_item = {"test": "data", "id": 1}
    await queue.put(test_item)
    
    assert await queue.empty() is False
    assert await queue.qsize() == 1
    
    retrieved_item = await queue.get(timeout=1.0)
    assert retrieved_item == test_item
    
    assert await queue.empty() is True
    assert await queue.qsize() == 0
    
    await queue.stop()


@pytest.mark.asyncio
async def test_memory_queue_timeout():
    """Test queue timeout behavior."""
    queue = MemoryQueue(maxsize=5)
    await queue.start()
    
    # Test timeout on empty queue
    with pytest.raises(asyncio.TimeoutError):
        await queue.get(timeout=0.1)
    
    await queue.stop()


@pytest.mark.asyncio
async def test_memory_queue_multiple_items():
    """Test queue with multiple items."""
    queue = MemoryQueue(maxsize=5)
    await queue.start()
    
    # Put multiple items
    items = [{"id": i, "data": f"test-{i}"} for i in range(3)]
    for item in items:
        await queue.put(item)
    
    assert await queue.qsize() == 3
    
    # Get items in order
    for expected_item in items:
        retrieved_item = await queue.get(timeout=1.0)
        assert retrieved_item == expected_item
    
    assert await queue.empty() is True
    
    await queue.stop()


@pytest.mark.asyncio
async def test_memory_queue_not_started():
    """Test queue operations before start."""
    queue = MemoryQueue(maxsize=5)
    
    with pytest.raises(RuntimeError, match="Queue not started"):
        await queue.put({"test": "data"})
    
    with pytest.raises(RuntimeError, match="Queue not started"):
        await queue.get(timeout=1.0)