"""In-memory queue implementation for terraform-indexer."""

import asyncio
from typing import Any, Dict, Optional

from .base import BaseQueue


class MemoryQueue(BaseQueue):
    """In-memory queue implementation using asyncio.Queue."""

    def __init__(self, maxsize: int = 0):
        """
        Initialize the memory queue.
        
        Args:
            maxsize: Maximum size of the queue. 0 means unlimited.
        """
        self.maxsize = maxsize
        self._queue: Optional[asyncio.Queue] = None

    async def start(self) -> None:
        """Initialize the queue."""
        self._queue = asyncio.Queue(maxsize=self.maxsize)

    async def stop(self) -> None:
        """Clean up the queue."""
        # Nothing to clean up for in-memory queue
        pass

    async def put(self, item: Dict[str, Any]) -> None:
        """Put an item into the queue."""
        if self._queue is None:
            raise RuntimeError("Queue not started. Call start() first.")
        await self._queue.put(item)

    async def get(self, timeout: Optional[float] = None) -> Dict[str, Any]:
        """Get an item from the queue."""
        if self._queue is None:
            raise RuntimeError("Queue not started. Call start() first.")
        
        if timeout is None:
            return await self._queue.get()
        else:
            return await asyncio.wait_for(self._queue.get(), timeout=timeout)

    async def empty(self) -> bool:
        """Return True if the queue is empty."""
        if self._queue is None:
            return True
        return self._queue.empty()

    async def qsize(self) -> int:
        """Return the approximate size of the queue."""
        if self._queue is None:
            return 0
        return self._queue.qsize()