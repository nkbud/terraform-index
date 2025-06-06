#!/usr/bin/env python3
"""End-to-end demo script."""

import asyncio
import sys
import os
import time
from pathlib import Path

# Add the src directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend" / "src"))

from indexer.collector.filesystem import FileSystemCollector
from indexer.collector.s3 import S3Collector
from indexer.collector.composite import CompositeCollector
from indexer.parser.tfstate import TfStateParser
from indexer.es import ElasticsearchSink
from indexer.queue.memory import MemoryQueue
from indexer.pipeline import CollectorWorker, ParserWorker, UploaderWorker


async def run_demo():
    """Run end-to-end pipeline demo."""
    print("Starting Terraform Indexer End-to-End Demo")
    print("=" * 50)
    
    # Initialize queues
    print("1. Initializing queues...")
    collector_queue = MemoryQueue(maxsize=100)
    parser_queue = MemoryQueue(maxsize=100)
    
    await collector_queue.start()
    await parser_queue.start()
    
    # Initialize collectors
    print("2. Setting up collectors...")
    collectors = []
    
    # Filesystem collector
    filesystem_collector = FileSystemCollector(
        watch_directory="./tfstates",
        poll_interval=3,
    )
    collectors.append(filesystem_collector)
    
    # S3 collector (for localstack)
    try:
        s3_collector = S3Collector(
            bucket_name="terraform-states",
            prefix="terraform/",
            poll_interval=5,
            aws_access_key_id="test",
            aws_secret_access_key="test",
            endpoint_url="http://localhost:4566",
        )
        collectors.append(s3_collector)
        print("   - S3 collector configured for localstack")
    except Exception as e:
        print(f"   - S3 collector failed to configure: {e}")
    
    print(f"   - Using {len(collectors)} collector(s)")
    
    # Create composite collector
    composite_collector = CompositeCollector(collectors)
    
    # Initialize parser and uploader
    print("3. Setting up parser and uploader...")
    parser = TfStateParser()
    
    es_sink = ElasticsearchSink(
        hosts="http://localhost:9200",
        index_name="terraform-resources-demo",
        batch_size=10,
        batch_timeout=5,
    )
    
    # Initialize workers
    print("4. Starting pipeline workers...")
    collector_worker = CollectorWorker(composite_collector, collector_queue)
    parser_worker = ParserWorker(collector_queue, parser_queue, parser)
    uploader_worker = UploaderWorker(parser_queue, es_sink)
    
    try:
        # Start workers
        await collector_worker.start()
        await parser_worker.start()
        await uploader_worker.start()
        
        print("5. Pipeline started! Processing files...")
        print("   - Collecting from filesystem and S3")
        print("   - Parsing terraform state files")
        print("   - Uploading to Elasticsearch")
        print("\nPress Ctrl+C to stop the demo\n")
        
        # Monitor queues
        start_time = time.time()
        while True:
            await asyncio.sleep(5)
            
            collector_size = await collector_queue.qsize()
            parser_size = await parser_queue.qsize()
            
            elapsed = int(time.time() - start_time)
            print(f"[{elapsed:3d}s] Queue sizes - Collector: {collector_size}, Parser: {parser_size}")
            
            # Auto-stop after 30 seconds for demo purposes
            if elapsed > 30:
                print("\nDemo time limit reached, stopping...")
                break
                
    except KeyboardInterrupt:
        print("\nStopping demo...")
    
    finally:
        # Clean up
        print("6. Cleaning up...")
        await uploader_worker.stop()
        await parser_worker.stop()
        await collector_worker.stop()
        
        await parser_queue.stop()
        await collector_queue.stop()
    
    print("Demo completed!")


if __name__ == "__main__":
    print("Terraform Indexer Demo")
    print("Make sure to start the required services first:")
    print("  docker compose up opensearch localstack")
    print("")
    
    try:
        asyncio.run(run_demo())
    except Exception as e:
        print(f"Demo failed: {e}")
        sys.exit(1)