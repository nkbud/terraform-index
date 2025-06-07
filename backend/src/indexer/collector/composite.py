"""Composite collector that combines multiple sources."""

import asyncio
from typing import AsyncIterator, Dict, Any, List

from .base import BaseCollector


class CompositeCollector(BaseCollector):
    """Collector that combines multiple collector sources."""

    def __init__(self, collectors: List[BaseCollector]):
        """
        Initialize composite collector.
        
        Args:
            collectors: List of collectors to combine
        """
        self.collectors = collectors
        self._running = False
        self._tasks: List[asyncio.Task] = []

    async def start(self) -> None:
        """Initialize all collectors."""
        self._running = True
        for collector in self.collectors:
            await collector.start()

    async def stop(self) -> None:
        """Clean up all collectors."""
        self._running = False
        
        # Cancel all running tasks
        for task in self._tasks:
            if not task.done():
                task.cancel()
        
        # Wait for tasks to complete
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        
        # Stop all collectors
        for collector in self.collectors:
            await collector.stop()

    async def collect(self) -> AsyncIterator[Dict[str, Any]]:
        """
        Collect from all sources concurrently.
        
        Yields:
            Dict with 'content' (parsed tfstate JSON) and 'metadata'
        """
        # Create a queue to collect items from all sources
        queue: asyncio.Queue = asyncio.Queue()
        
        async def collector_worker(collector: BaseCollector) -> None:
            """Worker function for a single collector."""
            try:
                async for item in collector.collect():
                    await queue.put(item)
            except Exception as e:
                print(f"Error in collector {type(collector).__name__}: {e}")
            finally:
                # Signal completion for this collector
                await queue.put(None)
        
        # Start all collector workers
        active_collectors = len(self.collectors)
        self._tasks = [
            asyncio.create_task(collector_worker(collector))
            for collector in self.collectors
        ]
        
        # Yield items as they become available
        while self._running and active_collectors > 0:
            try:
                item = await asyncio.wait_for(queue.get(), timeout=1.0)
                if item is None:
                    # One collector has finished
                    active_collectors -= 1
                else:
                    yield item
            except asyncio.TimeoutError:
                # Continue the loop to check _running status
                continue
            except Exception as e:
                print(f"Error in composite collector: {e}")
                await asyncio.sleep(1)