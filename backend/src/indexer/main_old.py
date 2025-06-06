"""Main application entry point for terraform-indexer."""

import asyncio
import os
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from pydantic_settings import BaseSettings

from indexer.collector.s3 import S3Collector
from indexer.parser.tfstate import TfStateParser
from indexer.es import ElasticsearchSink


class Settings(BaseSettings):
    """Application settings."""
    
    # S3 Configuration
    s3_bucket: str = "terraform-states"
    s3_prefix: str = ""
    s3_poll_interval: int = 30
    s3_endpoint_url: str = None
    aws_access_key_id: str = None
    aws_secret_access_key: str = None
    
    # Elasticsearch Configuration
    es_hosts: str = "http://localhost:9200"
    es_index: str = "terraform-resources"
    es_batch_size: int = 100
    es_batch_timeout: int = 10

    class Config:
        env_file = ".env"


# Global components
collector: S3Collector = None
parser: TfStateParser = None
es_sink: ElasticsearchSink = None
indexing_task: asyncio.Task = None
settings = Settings()


async def indexing_loop() -> None:
    """Main indexing loop that processes terraform state files."""
    global collector, parser, es_sink
    
    print("Starting indexing loop...")
    
    try:
        async for state_data in collector.collect():
            tfstate = state_data['content']
            metadata = state_data['metadata']
            
            print(f"Processing {metadata['key']} from {metadata['bucket']}")
            
            # Parse tfstate into individual resource documents
            for doc in parser.parse(tfstate, metadata):
                await es_sink.index_document(doc)
                
    except Exception as e:
        print(f"Error in indexing loop: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan manager."""
    global collector, parser, es_sink, indexing_task
    
    # Initialize components
    collector = S3Collector(
        bucket_name=settings.s3_bucket,
        prefix=settings.s3_prefix,
        poll_interval=settings.s3_poll_interval,
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
        endpoint_url=settings.s3_endpoint_url,
    )
    
    parser = TfStateParser()
    
    es_sink = ElasticsearchSink(
        hosts=settings.es_hosts,
        index_name=settings.es_index,
        batch_size=settings.es_batch_size,
        batch_timeout=settings.es_batch_timeout,
    )
    
    # Start services
    await collector.start()
    await es_sink.start()
    
    # Start background indexing task
    indexing_task = asyncio.create_task(indexing_loop())
    
    print("Terraform indexer started")
    
    yield
    
    # Cleanup
    print("Shutting down terraform indexer...")
    
    if indexing_task:
        indexing_task.cancel()
        try:
            await indexing_task
        except asyncio.CancelledError:
            pass
    
    await collector.stop()
    await es_sink.stop()


# Create FastAPI app
app = FastAPI(
    title="Terraform Indexer",
    description="Index Terraform state files into Elasticsearch",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/")
async def root():
    """Health check endpoint."""
    return {"status": "ok", "service": "terraform-indexer"}


@app.get("/stats")
async def get_stats():
    """Get indexing statistics."""
    if es_sink:
        try:
            stats = await es_sink.get_stats()
            return {
                "elasticsearch": stats,
                "collector": {
                    "bucket": settings.s3_bucket,
                    "prefix": settings.s3_prefix,
                    "poll_interval": settings.s3_poll_interval,
                }
            }
        except Exception as e:
            return {"error": str(e)}
    return {"error": "Service not initialized"}


@app.post("/search")
async def search_resources(query: dict):
    """Search terraform resources."""
    if es_sink:
        try:
            return await es_sink.search(query)
        except Exception as e:
            return {"error": str(e)}
    return {"error": "Service not initialized"}


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )