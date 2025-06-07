#!/usr/bin/env python3
"""Simple filesystem-only demo script."""

import asyncio
import sys
import time
from pathlib import Path

# Add the src directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend" / "src"))

from indexer.collector.filesystem import FileSystemCollector
from indexer.parser.tfstate import TfStateParser
from indexer.queue.memory import MemoryQueue
from indexer.pipeline import CollectorWorker, ParserWorker


async def run_filesystem_demo():
    """Run filesystem-only pipeline demo."""
    print("Starting Filesystem-Only Terraform Indexer Demo")
    print("=" * 50)
    
    # Initialize queues
    print("1. Initializing queues...")
    collector_queue = MemoryQueue(maxsize=100)
    parser_queue = MemoryQueue(maxsize=100)
    
    await collector_queue.start()
    await parser_queue.start()
    
    # Initialize filesystem collector
    print("2. Setting up filesystem collector...")
    filesystem_collector = FileSystemCollector(
        watch_directory="./tfstates",
        poll_interval=3,
    )
    
    # Initialize parser
    print("3. Setting up parser...")
    parser = TfStateParser()
    
    # Initialize workers
    print("4. Starting pipeline workers...")
    collector_worker = CollectorWorker(filesystem_collector, collector_queue)
    parser_worker = ParserWorker(collector_queue, parser_queue, parser)
    
    try:
        # Start workers
        await collector_worker.start()
        await parser_worker.start()
        
        print("5. Pipeline started! Processing files...")
        print("   - Collecting from ./tfstates directory")
        print("   - Parsing terraform state files")
        print("\nMonitoring for 20 seconds...\n")
        
        # Monitor queues
        start_time = time.time()
        processed_docs = 0
        
        while True:
            await asyncio.sleep(2)
            
            collector_size = await collector_queue.qsize()
            parser_size = await parser_queue.qsize()
            
            elapsed = int(time.time() - start_time)
            print(f"[{elapsed:3d}s] Queue sizes - Collector: {collector_size}, Parser: {parser_size}")
            
            # Check parser queue for processed documents
            try:
                while not await parser_queue.empty():
                    doc_item = await parser_queue.get(timeout=0.1)
                    doc = doc_item['document']
                    processed_docs += 1
                    print(f"      Processed: {doc['resource_type']}.{doc['resource_name']}")
            except asyncio.TimeoutError:
                pass
            
            # Auto-stop after 20 seconds for demo purposes
            if elapsed > 20:
                print(f"\nDemo completed! Processed {processed_docs} documents.")
                break
                
    except KeyboardInterrupt:
        print("\nStopping demo...")
    
    finally:
        # Clean up
        print("6. Cleaning up...")
        await parser_worker.stop()
        await collector_worker.stop()
        
        await parser_queue.stop()
        await collector_queue.stop()
    
    print("Demo completed!")


if __name__ == "__main__":
    print("Simple Filesystem Demo")
    print("Processing .tfstate files from ./tfstates directory")
    print("")
    
    try:
        asyncio.run(run_filesystem_demo())
    except Exception as e:
        print(f"Demo failed: {e}")
        sys.exit(1)