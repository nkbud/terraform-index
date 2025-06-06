"""Base collector interface for terraform-indexer."""

from abc import ABC, abstractmethod
from typing import AsyncIterator, Dict, Any


class BaseCollector(ABC):
    """Abstract base class for collecting terraform state files."""

    @abstractmethod
    async def collect(self) -> AsyncIterator[Dict[str, Any]]:
        """
        Collect terraform state files from a source.
        
        Yields:
            Dict containing 'content' (parsed JSON) and 'metadata' (source info)
        """
        pass

    @abstractmethod
    async def start(self) -> None:
        """Initialize the collector."""
        pass

    @abstractmethod
    async def stop(self) -> None:
        """Clean up the collector."""
        pass