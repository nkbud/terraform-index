"""Elasticsearch client and bulk indexing operations."""

import asyncio
from typing import Dict, Any, List, Optional
from elasticsearch import AsyncElasticsearch
from elasticsearch.helpers import async_bulk


class ElasticsearchSink:
    """Handles indexing documents to Elasticsearch."""

    def __init__(
        self,
        hosts: str = "http://localhost:9200",
        index_name: str = "terraform-resources",
        batch_size: int = 100,
        batch_timeout: int = 10,
    ):
        self.es_client = AsyncElasticsearch(hosts=[hosts])
        self.index_name = index_name
        self.batch_size = batch_size
        self.batch_timeout = batch_timeout
        self._batch: List[Dict[str, Any]] = []
        self._last_flush = asyncio.get_event_loop().time()

    async def start(self) -> None:
        """Initialize Elasticsearch connection and index."""
        # Test connection
        if not await self.es_client.ping():
            raise ConnectionError("Failed to connect to Elasticsearch")
        
        # Create index if it doesn't exist
        await self._ensure_index()

    async def stop(self) -> None:
        """Clean up and close connections."""
        # Flush any remaining documents
        await self.flush()
        await self.es_client.close()

    async def index_document(self, doc: Dict[str, Any]) -> None:
        """
        Add a document to the batch for indexing.
        
        Args:
            doc: Document to index
        """
        self._batch.append({
            '_index': self.index_name,
            '_id': doc.get('id'),
            '_source': doc,
        })
        
        # Check if we should flush
        current_time = asyncio.get_event_loop().time()
        should_flush = (
            len(self._batch) >= self.batch_size or
            current_time - self._last_flush >= self.batch_timeout
        )
        
        if should_flush:
            await self.flush()

    async def flush(self) -> None:
        """Flush current batch to Elasticsearch."""
        if not self._batch:
            return
        
        try:
            # Bulk index documents
            success, failed = await async_bulk(
                self.es_client,
                self._batch,
                refresh=True,
            )
            
            print(f"Indexed {success} documents, {len(failed)} failed")
            
            if failed:
                for failure in failed:
                    print(f"Index failure: {failure}")
            
        except Exception as e:
            print(f"Bulk index error: {e}")
        finally:
            self._batch.clear()
            self._last_flush = asyncio.get_event_loop().time()

    async def _ensure_index(self) -> None:
        """Create index with appropriate mapping if it doesn't exist."""
        index_exists = await self.es_client.indices.exists(index=self.index_name)
        
        if not index_exists:
            mapping = {
                "mappings": {
                    "properties": {
                        "id": {"type": "keyword"},
                        "state_version": {"type": "integer"},
                        "terraform_version": {"type": "keyword"},
                        "resource_type": {"type": "keyword"},
                        "resource_name": {"type": "keyword"},
                        "resource_mode": {"type": "keyword"},
                        "provider": {"type": "keyword"},
                        "instance_index": {"type": "integer"},
                        "source_bucket": {"type": "keyword"},
                        "source_key": {"type": "keyword"},
                        "source_last_modified": {"type": "date"},
                        "indexed_at": {"type": "date"},
                        "attributes": {"type": "object", "enabled": False},
                    }
                },
                "settings": {
                    "number_of_shards": 1,
                    "number_of_replicas": 0,
                }
            }
            
            await self.es_client.indices.create(
                index=self.index_name,
                body=mapping
            )
            print(f"Created index: {self.index_name}")

    async def search(self, query: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a search query."""
        return await self.es_client.search(
            index=self.index_name,
            body=query
        )

    async def get_stats(self) -> Dict[str, Any]:
        """Get index statistics."""
        return await self.es_client.indices.stats(index=self.index_name)