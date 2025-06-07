"""Pipeline components for queue-based architecture."""

import asyncio
import time
from typing import Dict, Any, TYPE_CHECKING

from .queue.base import BaseQueue
from .collector.base import BaseCollector
from .parser.tfstate import TfStateParser
from .logging import LoggingMixin

if TYPE_CHECKING:
    from .es import ElasticsearchSink


class CollectorWorker(LoggingMixin):
    """Worker that reads from collector and puts items in queue."""
    
    def __init__(self, collector: BaseCollector, output_queue: BaseQueue):
        self.collector = collector
        self.output_queue = output_queue
        self._running = False
        self._task: asyncio.Task = None
        self._collected_count = 0
        self._start_time = None

    async def start(self) -> None:
        """Start the collector worker."""
        self.logger.info("🔍 Starting collector worker...")
        self._running = True
        self._start_time = time.time()
        await self.collector.start()
        self._task = asyncio.create_task(self._run())
        self.logger.info("✅ Collector worker started")

    async def stop(self) -> None:
        """Stop the collector worker."""
        self.logger.info("🛑 Stopping collector worker...")
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                self.logger.debug("Collector worker task cancelled")
        await self.collector.stop()
        
        runtime = time.time() - self._start_time if self._start_time else 0
        self.logger.info(f"✅ Collector worker stopped (processed {self._collected_count} items in {runtime:.2f}s)")

    async def _run(self) -> None:
        """Main worker loop."""
        self.logger.debug("Collector worker loop started")
        try:
            async for item in self.collector.collect():
                if not self._running:
                    self.logger.debug("Collector worker stopping...")
                    break
                
                self._collected_count += 1
                await self.output_queue.put(item)
                
                # Log progress every 10 items or every 30 seconds
                if self._collected_count % 10 == 0:
                    queue_size = await self.output_queue.qsize()
                    runtime = time.time() - self._start_time
                    rate = self._collected_count / runtime if runtime > 0 else 0
                    self.logger.info(f"📈 Collected {self._collected_count} items ({rate:.1f}/sec), queue size: {queue_size}")
                else:
                    self.logger.debug(f"Collected item #{self._collected_count}")
                    
        except Exception as e:
            self.logger.error(f"❌ Error in collector worker: {e}")
            self.logger.exception("Full error details:")


class ParserWorker(LoggingMixin):
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
        self._parsed_count = 0
        self._resources_count = 0
        self._start_time = None

    async def start(self) -> None:
        """Start the parser worker."""
        self.logger.info("🔧 Starting parser worker...")
        self._running = True
        self._start_time = time.time()
        self._task = asyncio.create_task(self._run())
        self.logger.info("✅ Parser worker started")

    async def stop(self) -> None:
        """Stop the parser worker."""
        self.logger.info("🛑 Stopping parser worker...")
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                self.logger.debug("Parser worker task cancelled")
        
        runtime = time.time() - self._start_time if self._start_time else 0
        self.logger.info(f"✅ Parser worker stopped (parsed {self._parsed_count} files, {self._resources_count} resources in {runtime:.2f}s)")

    async def _run(self) -> None:
        """Main worker loop."""
        self.logger.debug("Parser worker loop started")
        
        while self._running:
            try:
                # Get item from input queue with timeout
                item = await self.input_queue.get(timeout=1.0)
                if item is None:
                    continue
                
                # Parse the tfstate content
                tfstate = item['content']
                metadata = item['metadata']
                
                self.logger.debug(f"Parsing item from {metadata.get('source', 'unknown')}")
                
                try:
                    # Parse and send each document to output queue
                    resource_count = 0
                    for doc in self.parser.parse(tfstate, metadata):
                        await self.output_queue.put({
                            'document': doc,
                            'metadata': metadata
                        })
                        resource_count += 1
                    
                    self._parsed_count += 1
                    self._resources_count += resource_count
                    
                    self.logger.debug(f"Parsed {resource_count} resources from {metadata.get('source', 'unknown')}")
                    
                    # Log progress
                    if self._parsed_count % 5 == 0 or resource_count > 10:
                        input_queue_size = await self.input_queue.qsize()
                        output_queue_size = await self.output_queue.qsize()
                        runtime = time.time() - self._start_time
                        rate = self._resources_count / runtime if runtime > 0 else 0
                        self.logger.info(f"🔧 Parsed {self._parsed_count} files → {self._resources_count} resources ({rate:.1f}/sec), queues: {input_queue_size}→{output_queue_size}")
                        
                except Exception as e:
                    self.logger.error(f"❌ Failed to parse item: {e}")
                    self.logger.debug(f"Failed item metadata: {metadata}")
                    
            except asyncio.TimeoutError:
                # Continue loop to check _running status
                continue
            except Exception as e:
                self.logger.error(f"❌ Error in parser worker: {e}")
                self.logger.exception("Full error details:")
                await asyncio.sleep(1)


class UploaderWorker(LoggingMixin):
    """Worker that reads from input queue and uploads to Elasticsearch."""
    
    def __init__(self, input_queue: BaseQueue, uploader):
        self.input_queue = input_queue
        self.uploader = uploader
        self._running = False
        self._task: asyncio.Task = None
        self._uploaded_count = 0
        self._start_time = None

    async def start(self) -> None:
        """Start the uploader worker."""
        self.logger.info("📤 Starting uploader worker...")
        self._running = True
        self._start_time = time.time()
        await self.uploader.start()
        self._task = asyncio.create_task(self._run())
        self.logger.info("✅ Uploader worker started")

    async def stop(self) -> None:
        """Stop the uploader worker."""
        self.logger.info("🛑 Stopping uploader worker...")
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                self.logger.debug("Uploader worker task cancelled")
        
        # Flush any remaining items
        try:
            await self.uploader.stop()
            self.logger.debug("Flushed remaining items to Elasticsearch")
        except Exception as e:
            self.logger.warning(f"Failed to flush during shutdown: {e}")
        
        runtime = time.time() - self._start_time if self._start_time else 0
        self.logger.info(f"✅ Uploader worker stopped (uploaded {self._uploaded_count} documents in {runtime:.2f}s)")

    async def _run(self) -> None:
        """Main worker loop."""
        self.logger.debug("Uploader worker loop started")
        
        while self._running:
            try:
                # Get item from input queue with timeout
                item = await self.input_queue.get(timeout=1.0)
                if item is None:
                    continue
                
                # Upload the document
                document = item['document']
                
                try:
                    await self.uploader.index_document(document)
                    self._uploaded_count += 1
                    
                    self.logger.debug(f"Uploaded document: {document.get('id', 'unknown')}")
                    
                    # Log progress every 25 uploads
                    if self._uploaded_count % 25 == 0:
                        queue_size = await self.input_queue.qsize()
                        runtime = time.time() - self._start_time
                        rate = self._uploaded_count / runtime if runtime > 0 else 0
                        self.logger.info(f"📤 Uploaded {self._uploaded_count} documents ({rate:.1f}/sec), queue size: {queue_size}")
                        
                except Exception as e:
                    self.logger.error(f"❌ Failed to upload document: {e}")
                    self.logger.debug(f"Failed document ID: {document.get('id', 'unknown')}")
                    
            except asyncio.TimeoutError:
                # Continue loop to check _running status
                continue
            except Exception as e:
                self.logger.error(f"❌ Error in uploader worker: {e}")
                self.logger.exception("Full error details:")
                await asyncio.sleep(1)