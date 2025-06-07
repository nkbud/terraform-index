"""Base queue interface for terraform-indexer."""

import asyncio
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class BaseQueue(ABC):
    """Abstract base class for queue implementations."""

    @abstractmethod
    async def put(self, item: Dict[str, Any]) -> None:
        """Put an item into the queue."""
        pass

    @abstractmethod
    async def get(self, timeout: Optional[float] = None) -> Dict[str, Any]:
        """Get an item from the queue. Raises asyncio.TimeoutError if timeout is reached."""
        pass

    @abstractmethod
    async def empty(self) -> bool:
        """Return True if the queue is empty."""
        pass

    @abstractmethod
    async def qsize(self) -> int:
        """Return the approximate size of the queue."""
        pass

    @abstractmethod
    async def start(self) -> None:
        """Initialize the queue."""
        pass

    @abstractmethod
    async def stop(self) -> None:
        """Clean up the queue."""
        pass