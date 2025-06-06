#!/usr/bin/env python3
"""Script to run individual pipeline components for testing."""

import asyncio
import sys
import os
from pathlib import Path

# Add the src directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend" / "src"))


async def run_filesystem_collector():
    """Test the filesystem collector."""
    print("Testing filesystem collector...")
    
    from indexer.collector.filesystem import FileSystemCollector
    
    collector = FileSystemCollector(
        watch_directory="./tfstates",
        poll_interval=2,
    )
    
    await collector.start()
    
    try:
        count = 0
        async for item in collector.collect():
            print(f"Collected: {item['metadata']['path']}")
            count += 1
            if count >= 5:  # Limit for demo
                break
    except KeyboardInterrupt:
        print("\nStopping collector...")
    finally:
        await collector.stop()


async def run_s3_collector():
    """Test the S3 collector with localstack."""
    print("Testing S3 collector with localstack...")
    
    try:
        from indexer.collector.s3 import S3Collector
    except ImportError as e:
        print(f"Cannot test S3 collector - missing dependencies: {e}")
        return
    
    collector = S3Collector(
        bucket_name="terraform-states",
        prefix="terraform/",
        poll_interval=5,
        aws_access_key_id="test",
        aws_secret_access_key="test",
        endpoint_url="http://localhost:4566",
    )
    
    try:
        await collector.start()
    except Exception as e:
        print(f"Failed to start S3 collector (is localstack running?): {e}")
        return
    
    try:
        count = 0
        async for item in collector.collect():
            print(f"Collected: {item['metadata']['key']}")
            count += 1
            if count >= 5:  # Limit for demo
                break
    except KeyboardInterrupt:
        print("\nStopping collector...")
    finally:
        await collector.stop()


async def run_parser_test():
    """Test the parser."""
    print("Testing parser...")
    
    from indexer.parser.tfstate import TfStateParser
    
    parser = TfStateParser()
    
    # Load a sample file
    sample_file = Path("./tfstates/example-web-app.tfstate")
    if not sample_file.exists():
        print(f"Sample file {sample_file} not found")
        return
    
    import json
    with open(sample_file) as f:
        tfstate = json.load(f)
    
    metadata = {
        'source': 'test',
        'path': str(sample_file),
        'collected_at': '2024-01-01T00:00:00Z',
    }
    
    print("Parsing tfstate file...")
    for doc in parser.parse(tfstate, metadata):
        print(f"Parsed document: {doc['resource_type']}.{doc['resource_name']}")


async def run_queue_test():
    """Test the queue."""
    print("Testing memory queue...")
    
    from indexer.queue.memory import MemoryQueue
    
    queue = MemoryQueue(maxsize=10)
    await queue.start()
    
    # Put some items
    for i in range(3):
        await queue.put({"id": i, "data": f"test-{i}"})
        print(f"Put item {i}")
    
    print(f"Queue size: {await queue.qsize()}")
    
    # Get items
    while not await queue.empty():
        item = await queue.get(timeout=1.0)
        print(f"Got item: {item}")
    
    await queue.stop()


async def main():
    """Main function."""
    if len(sys.argv) < 2:
        print("Usage: python run_component.py <component>")
        print("Components: filesystem, s3, parser, queue")
        return
    
    component = sys.argv[1].lower()
    
    if component == "filesystem":
        await run_filesystem_collector()
    elif component == "s3":
        await run_s3_collector()
    elif component == "parser":
        await run_parser_test()
    elif component == "queue":
        await run_queue_test()
    else:
        print(f"Unknown component: {component}")
        print("Available components: filesystem, s3, parser, queue")


if __name__ == "__main__":
    asyncio.run(main())