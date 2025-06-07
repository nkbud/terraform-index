"""Main application entry point for terraform-indexer."""

import asyncio
import json
import os
import time
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
from indexer.logging import setup_logging, get_logger


class Settings(BaseSettings):
    """Application settings."""
    
    # Mode configuration
    mode: str = "local"  # "local" or "prod"
    
    # Logging configuration
    log_level: str = "INFO"  # DEBUG, INFO, WARNING, ERROR
    log_format: str = "simple"  # simple, detailed, json
    
    # S3 Configuration (JSON string for multiple buckets)
    s3_buckets: str = '["terraform-states"]'  # JSON string of bucket names
    s3_poll_interval: int = 30
    s3_endpoint_url: str = None
    aws_access_key_id: str = None
    aws_secret_access_key: str = None
    
    # Elasticsearch Configuration (JSON string for multiple hosts)
    es_hosts: str = '["http://localhost:9200"]'  # JSON string of host URLs
    es_index: str = "terraform-resources"
    es_batch_size: int = 100
    es_batch_timeout: int = 10
    
    # Filesystem Configuration
    filesystem_watch_directory: str = "./tfstates"
    filesystem_poll_interval: int = 5
    filesystem_enabled: bool = True
    
    # Kubernetes Configuration
    kubernetes_enabled: bool = False
    kubernetes_poll_interval: int = 60
    kubernetes_secret_label_selector: str = "app.terraform.io/component=backend-state"
    kubernetes_secret_name_pattern: str = "tfstate-"
    kubernetes_clusters: str = "[]"  # JSON string of cluster configurations
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

# Setup logging
setup_logging(level=settings.log_level, format_type=settings.log_format)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan manager."""
    global collector_queue, parser_queue, collector_worker, parser_worker, uploader_worker
    
    start_time = time.time()
    logger.info(f"🚀 Starting terraform indexer in {settings.mode} mode...")
    logger.debug(f"Configuration: {settings.dict()}")
    
    try:
    try:
        # Parse JSON configurations
        s3_buckets = json.loads(settings.s3_buckets)
        es_hosts = json.loads(settings.es_hosts)
        
        # Initialize queues (unlimited size)
        logger.info("📋 Initializing queues...")
        collector_queue = MemoryQueue()
        parser_queue = MemoryQueue()
        
        await collector_queue.start()
        await parser_queue.start()
        logger.debug("✅ Queues initialized successfully")
        
        # Initialize collectors based on mode
        logger.info(f"🔧 Setting up collectors for {settings.mode} mode...")
        collectors = []
        
        if settings.mode == "local":
            # Local mode: use both filesystem and localstack S3
            if settings.filesystem_enabled:
                logger.info(f"📁 Adding filesystem collector (watching: {settings.filesystem_watch_directory})")
                filesystem_collector = FileSystemCollector(
                    watch_directory=settings.filesystem_watch_directory,
                    poll_interval=settings.filesystem_poll_interval,
                )
                collectors.append(filesystem_collector)
            
            # Add S3 collector for localstack
            logger.info(f"☁️ Adding S3 collector for localstack (buckets: {s3_buckets})")
            s3_collector = S3Collector(
                bucket_names=s3_buckets,
                poll_interval=settings.s3_poll_interval,
                aws_access_key_id=settings.aws_access_key_id or "test",
                aws_secret_access_key=settings.aws_secret_access_key or "test",
                endpoint_url=settings.s3_endpoint_url or "http://localhost:4566",
            )
            collectors.append(s3_collector)
            
        else:
            # Production mode: use real S3
            logger.info(f"☁️ Adding S3 collector for AWS (buckets: {s3_buckets})")
            s3_collector = S3Collector(
                bucket_names=s3_buckets,
                poll_interval=settings.s3_poll_interval,
                aws_access_key_id=settings.aws_access_key_id,
                aws_secret_access_key=settings.aws_secret_access_key,
                endpoint_url=settings.s3_endpoint_url,
            )
            collectors.append(s3_collector)
        
        # Add Kubernetes collector if enabled
        if settings.kubernetes_enabled:
            logger.info("⚓ Setting up Kubernetes collector...")
            try:
                # Parse clusters configuration from JSON string
                k8s_clusters = json.loads(settings.kubernetes_clusters)
                
                if k8s_clusters:
                    kubernetes_collector = KubernetesCollector(
                        clusters=k8s_clusters,
                        poll_interval=settings.kubernetes_poll_interval,
                        secret_label_selector=settings.kubernetes_secret_label_selector,
                        secret_name_pattern=settings.kubernetes_secret_name_pattern,
                    )
                    collectors.append(kubernetes_collector)
                    logger.info(f"✅ Kubernetes collector initialized with {len(k8s_clusters)} clusters")
                else:
                    logger.warning("⚠️ Kubernetes collector enabled but no clusters configured")
                    
            except json.JSONDecodeError as e:
                logger.error(f"❌ Failed to parse Kubernetes clusters configuration: {e}")
            except Exception as e:
                logger.error(f"❌ Failed to initialize Kubernetes collector: {e}")
        
        # Create composite collector
        logger.info(f"🔀 Creating composite collector with {len(collectors)} sources")
        composite_collector = CompositeCollector(collectors)
        
        # Initialize parser
        logger.info("🔍 Initializing Terraform state parser...")
        parser = TfStateParser()
        
        # Initialize Elasticsearch sink
        logger.info(f"📊 Initializing Elasticsearch sink (index: {settings.es_index})...")
        es_sink = ElasticsearchSink(
            hosts=es_hosts,
            index_name=settings.es_index,
        batch_size=settings.es_batch_size,
        batch_timeout=settings.es_batch_timeout,
    )
    
    # Initialize workers
    logger.info("👷 Starting pipeline workers...")
    collector_worker = CollectorWorker(composite_collector, collector_queue)
    parser_worker = ParserWorker(collector_queue, parser_queue, parser)
    uploader_worker = UploaderWorker(parser_queue, es_sink)
    
    # Start workers
    await collector_worker.start()
    await parser_worker.start()
    await uploader_worker.start()
    
    startup_time = time.time() - start_time
    logger.info(f"🎉 Terraform indexer started successfully in {startup_time:.2f}s")
    logger.info(f"🌐 API available at: http://localhost:8000")
    logger.info(f"📊 Stats endpoint: http://localhost:8000/stats")
    logger.info(f"📖 API docs: http://localhost:8000/docs")
    
    yield
    
    # Cleanup
    logger.info("🛑 Shutting down terraform indexer...")
    
    if uploader_worker:
        logger.debug("Stopping uploader worker...")
        await uploader_worker.stop()
    if parser_worker:
        logger.debug("Stopping parser worker...")
        await parser_worker.stop()
    if collector_worker:
        logger.debug("Stopping collector worker...")
        await collector_worker.stop()
    
    if parser_queue:
        logger.debug("Stopping parser queue...")
        await parser_queue.stop()
    if collector_queue:
        logger.debug("Stopping collector queue...")
        await collector_queue.stop()
    
    logger.info("✅ Terraform indexer shut down complete")
    
    except Exception as e:
        logger.error(f"❌ Failed to start terraform indexer: {e}")
        logger.exception("Full error details:")
        raise


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
    logger.debug("Health check requested")
    return {"status": "ok", "service": "terraform-indexer", "mode": settings.mode}


@app.get("/stats")
async def get_stats():
    """Get indexing statistics."""
    global collector_queue, parser_queue, uploader_worker
    
    logger.debug("Stats requested")
    
    try:
        s3_buckets = json.loads(settings.s3_buckets)
        k8s_clusters = json.loads(settings.kubernetes_clusters) if settings.kubernetes_clusters else []
    except json.JSONDecodeError:
        s3_buckets = ["ERROR: Invalid JSON"]
        k8s_clusters = []
    
    stats = {
        "mode": settings.mode,
        "queues": {},
        "collector": {
            "buckets": s3_buckets,
            "poll_interval": settings.s3_poll_interval,
        },
        "kubernetes": {
            "enabled": settings.kubernetes_enabled,
            "poll_interval": settings.kubernetes_poll_interval,
            "clusters": k8s_clusters if settings.kubernetes_enabled else None,
        }
    }
    
    if collector_queue:
        queue_size = await collector_queue.qsize()
        stats["queues"]["collector_queue_size"] = queue_size
        logger.debug(f"Collector queue size: {queue_size}")
    if parser_queue:
        queue_size = await parser_queue.qsize()
        stats["queues"]["parser_queue_size"] = queue_size
        logger.debug(f"Parser queue size: {queue_size}")
    
    if uploader_worker and uploader_worker.uploader:
        try:
            es_stats = await uploader_worker.uploader.get_stats()
            stats["elasticsearch"] = es_stats
            logger.debug(f"Elasticsearch stats: {es_stats}")
        except Exception as e:
            stats["elasticsearch_error"] = str(e)
            logger.warning(f"Failed to get Elasticsearch stats: {e}")
    
    return stats


@app.post("/search")
async def search_resources(query: dict):
    """Search terraform resources."""
    global uploader_worker
    
    logger.debug(f"Search requested with query: {query}")
    
    if uploader_worker and uploader_worker.uploader:
        try:
            result = await uploader_worker.uploader.search(query)
            logger.debug(f"Search returned {len(result.get('hits', {}).get('hits', []))} results")
            return result
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return {"error": str(e)}
    
    logger.warning("Search requested but service not initialized")
    return {"error": "Service not initialized"}


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )