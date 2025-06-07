"""Main application entry point for terraform-indexer."""

import asyncio
import json
import os
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from pydantic_settings import BaseSettings

from indexer.collector.s3 import S3Collector
from indexer.collector.filesystem import FileSystemCollector
from indexer.collector.composite import CompositeCollector
from indexer.collector.kubernetes import KubernetesCollector
from indexer.parser.tfstate import TfStateParser
from indexer.es import ElasticsearchSink
from indexer.queue.memory import MemoryQueue
from indexer.pipeline import CollectorWorker, ParserWorker, UploaderWorker


class Settings(BaseSettings):
    """Application settings."""
    
    # Mode configuration
    mode: str = "local"  # "local" or "cloud"
    
    # S3 Configuration
    s3_buckets: str = "terraform-states"  # comma-separated list
    s3_poll_interval: int = 30
    s3_endpoint_url: str = None
    aws_access_key_id: str = None
    aws_secret_access_key: str = None
    
    # Filesystem Configuration
    filesystem_watch_directory: str = "./tfstates"
    filesystem_poll_interval: int = 5
    filesystem_enabled: bool = True
    
    # Kubernetes Configuration
    kubernetes_enabled: bool = False
    kubernetes_poll_interval: int = 60
    kubernetes_secret_label_selector: str = "app.terraform.io/component=backend-state"
    kubernetes_secret_name_pattern: str = "tfstate-"
    kubernetes_clusters: str = ""  # JSON string of cluster configurations
    
    # Elasticsearch Configuration
    es_hosts: str = "http://localhost:9200"
    es_index: str = "terraform-resources"
    es_batch_size: int = 100
    es_batch_timeout: int = 10
    
    # Queue Configuration (removed max size)
    # Queues are now unlimited by default

    class Config:
        env_file = ".env"


# Global components
collector_queue: MemoryQueue = None
parser_queue: MemoryQueue = None
collector_worker: CollectorWorker = None
parser_worker: ParserWorker = None
uploader_worker: UploaderWorker = None
settings = Settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan manager."""
    global collector_queue, parser_queue, collector_worker, parser_worker, uploader_worker
    
    print(f"Starting terraform indexer in {settings.mode} mode...")
    
    # Initialize queues (unlimited size)
    collector_queue = MemoryQueue()
    parser_queue = MemoryQueue()
    
    await collector_queue.start()
    await parser_queue.start()
    
    # Initialize collectors based on mode
    collectors = []
    
    if settings.mode == "local":
        # Local mode: use both filesystem and localstack S3
        if settings.filesystem_enabled:
            filesystem_collector = FileSystemCollector(
                watch_directory=settings.filesystem_watch_directory,
                poll_interval=settings.filesystem_poll_interval,
            )
            collectors.append(filesystem_collector)
        
        # Add S3 collector for localstack
        s3_collector = S3Collector(
            bucket_names=settings.s3_buckets,
            poll_interval=settings.s3_poll_interval,
            aws_access_key_id=settings.aws_access_key_id or "test",
            aws_secret_access_key=settings.aws_secret_access_key or "test",
            endpoint_url=settings.s3_endpoint_url or "http://localhost:4566",
        )
        collectors.append(s3_collector)
        
    else:
        # Cloud mode: use real S3
        s3_collector = S3Collector(
            bucket_names=settings.s3_buckets,
            poll_interval=settings.s3_poll_interval,
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
            endpoint_url=settings.s3_endpoint_url,
        )
        collectors.append(s3_collector)
    
    # Add Kubernetes collector if enabled
    if settings.kubernetes_enabled:
        try:
            # Parse clusters configuration from JSON string
            k8s_clusters = []
            if settings.kubernetes_clusters:
                k8s_clusters = json.loads(settings.kubernetes_clusters)
            
            if k8s_clusters:
                kubernetes_collector = KubernetesCollector(
                    clusters=k8s_clusters,
                    poll_interval=settings.kubernetes_poll_interval,
                    secret_label_selector=settings.kubernetes_secret_label_selector,
                    secret_name_pattern=settings.kubernetes_secret_name_pattern,
                )
                collectors.append(kubernetes_collector)
                print(f"Kubernetes collector initialized with {len(k8s_clusters)} clusters")
            else:
                print("Kubernetes collector enabled but no clusters configured")
                
        except json.JSONDecodeError as e:
            print(f"Failed to parse Kubernetes clusters configuration: {e}")
        except Exception as e:
            print(f"Failed to initialize Kubernetes collector: {e}")
    
    # Create composite collector
    composite_collector = CompositeCollector(collectors)
    
    # Initialize parser
    parser = TfStateParser()
    
    # Initialize Elasticsearch sink
    es_sink = ElasticsearchSink(
        hosts=settings.es_hosts,
        index_name=settings.es_index,
        batch_size=settings.es_batch_size,
        batch_timeout=settings.es_batch_timeout,
    )
    
    # Initialize workers
    collector_worker = CollectorWorker(composite_collector, collector_queue)
    parser_worker = ParserWorker(collector_queue, parser_queue, parser)
    uploader_worker = UploaderWorker(parser_queue, es_sink)
    
    # Start workers
    await collector_worker.start()
    await parser_worker.start()
    await uploader_worker.start()
    
    print("Terraform indexer started successfully")
    
    yield
    
    # Cleanup
    print("Shutting down terraform indexer...")
    
    if uploader_worker:
        await uploader_worker.stop()
    if parser_worker:
        await parser_worker.stop()
    if collector_worker:
        await collector_worker.stop()
    
    if parser_queue:
        await parser_queue.stop()
    if collector_queue:
        await collector_queue.stop()
    
    print("Terraform indexer shut down complete")


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
    return {"status": "ok", "service": "terraform-indexer", "mode": settings.mode}


@app.get("/stats")
async def get_stats():
    """Get indexing statistics."""
    global collector_queue, parser_queue, uploader_worker
    
    stats = {
        "mode": settings.mode,
        "queues": {},
        "collector": {
            "buckets": settings.s3_buckets,
            "poll_interval": settings.s3_poll_interval,
        },
        "kubernetes": {
            "enabled": settings.kubernetes_enabled,
            "poll_interval": settings.kubernetes_poll_interval,
            "clusters": settings.kubernetes_clusters if settings.kubernetes_enabled else None,
        }
    }
    
    if collector_queue:
        stats["queues"]["collector_queue_size"] = await collector_queue.qsize()
    if parser_queue:
        stats["queues"]["parser_queue_size"] = await parser_queue.qsize()
    
    if uploader_worker and uploader_worker.uploader:
        try:
            es_stats = await uploader_worker.uploader.get_stats()
            stats["elasticsearch"] = es_stats
        except Exception as e:
            stats["elasticsearch_error"] = str(e)
    
    return stats


@app.post("/search")
async def search_resources(query: dict):
    """Search terraform resources."""
    global uploader_worker
    
    if uploader_worker and uploader_worker.uploader:
        try:
            return await uploader_worker.uploader.search(query)
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