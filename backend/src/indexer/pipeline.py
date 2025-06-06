"""Pipeline components for queue-based architecture."""

import asyncio
from typing import Dict, Any, TYPE_CHECKING

from .queue.base import BaseQueue
from .collector.base import BaseCollector
from .parser.tfstate import TfStateParser

if TYPE_CHECKING:
    from .es import ElasticsearchSink


class CollectorWorker:
    """Worker that reads from collector and puts items in queue."""
    
    def __init__(self, collector: BaseCollector, output_queue: BaseQueue):
        self.collector = collector
        self.output_queue = output_queue
        self._running = False
        self._task: asyncio.Task = None

    async def start(self) -> None:
        """Start the collector worker."""
        self._running = True
        await self.collector.start()
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        """Stop the collector worker."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        await self.collector.stop()

    async def _run(self) -> None:
        """Main worker loop."""
        try:
            async for item in self.collector.collect():
                if not self._running:
                    break
                await self.output_queue.put(item)
        except Exception as e:
            print(f"Error in collector worker: {e}")


class ParserWorker:
    """Worker that reads from input queue, parses, and puts to output queue."""
    
    def __init__(
        self, 
        input_queue: BaseQueue, 
        output_queue: BaseQueue, 
        parser: TfStateParser
    ):
        self.input_queue = input_queue
        self.output_queue = output_queue
        self.parser = parser
        self._running = False
        self._task: asyncio.Task = None

    async def start(self) -> None:
        """Start the parser worker."""
        self._running = True
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        """Stop the parser worker."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _run(self) -> None:
        """Main worker loop."""
        while self._running:
            try:
                # Get item from input queue with timeout
                item = await self.input_queue.get(timeout=1.0)
                
                # Parse the tfstate content
                tfstate = item['content']
                metadata = item['metadata']
                
                # Parse and send each document to output queue
                for doc in self.parser.parse(tfstate, metadata):
                    await self.output_queue.put({
                        'document': doc,
                        'metadata': metadata
                    })
                    
            except asyncio.TimeoutError:
                # Continue loop to check _running status
                continue
            except Exception as e:
                print(f"Error in parser worker: {e}")
                await asyncio.sleep(1)


class UploaderWorker:
    """Worker that reads from input queue and uploads to Elasticsearch."""
    
    def __init__(self, input_queue: BaseQueue, uploader):
        self.input_queue = input_queue
        self.uploader = uploader
        self._running = False
        self._task: asyncio.Task = None

    async def start(self) -> None:
        """Start the uploader worker."""
        self._running = True
        await self.uploader.start()
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        """Stop the uploader worker."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        await self.uploader.stop()

    async def _run(self) -> None:
        """Main worker loop."""
        while self._running:
            try:
                # Get item from input queue with timeout
                item = await self.input_queue.get(timeout=1.0)
                
                # Upload the document
                document = item['document']
                await self.uploader.index_document(document)
                    
            except asyncio.TimeoutError:
                # Continue loop to check _running status
                continue
            except Exception as e:
                print(f"Error in uploader worker: {e}")
                await asyncio.sleep(1)