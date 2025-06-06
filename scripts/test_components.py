#!/usr/bin/env python3
"""Simple test runner without pytest."""

import asyncio
import sys
from pathlib import Path

# Add the src directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend" / "src"))

from indexer.parser.tfstate import TfStateParser
from indexer.queue.memory import MemoryQueue


def test_parser_filesystem():
    """Test parser with filesystem metadata."""
    print("Testing parser with filesystem metadata...")
    
    parser = TfStateParser()
    
    tfstate = {
        "version": 4,
        "terraform_version": "1.5.0",
        "resources": [
            {
                "mode": "managed",
                "type": "aws_instance",
                "name": "web",
                "provider": "provider[\"registry.terraform.io/hashicorp/aws\"]",
                "instances": [
                    {
                        "schema_version": 1,
                        "attributes": {
                            "id": "i-12345",
                            "instance_type": "t3.micro",
                            "tags": {
                                "Name": "WebServer",
                                "Environment": "test"
                            }
                        }
                    }
                ]
            }
        ]
    }
    
    metadata = {
        'source': 'filesystem',
        'path': '/path/to/test.tfstate',
        'size': 1024,
        'last_modified': '2024-01-01T12:00:00Z',
        'collected_at': '2024-01-01T12:00:00Z',
    }
    
    docs = list(parser.parse(tfstate, metadata))
    
    assert len(docs) == 1
    doc = docs[0]
    
    # Check ID format for filesystem source
    assert doc['id'] == '/path/to/test.tfstate/aws_instance.web.0'
    
    # Check source metadata
    assert doc['source_type'] == 'filesystem'
    assert doc['source_path'] == '/path/to/test.tfstate'
    assert doc['source_bucket'] is None
    assert doc['source_key'] is None
    
    # Check resource metadata
    assert doc['resource_type'] == 'aws_instance'
    assert doc['resource_name'] == 'web'
    assert doc['instance_index'] == 0
    
    # Check flattened attributes
    assert doc['attr_id'] == 'i-12345'
    assert doc['attr_instance_type'] == 't3.micro'
    assert doc['attr_tags_Name'] == 'WebServer'
    assert doc['attr_tags_Environment'] == 'test'
    
    print("✓ Parser filesystem test passed!")


def test_parser_s3():
    """Test parser with S3 metadata."""
    print("Testing parser with S3 metadata...")
    
    parser = TfStateParser()
    
    tfstate = {
        "version": 4,
        "terraform_version": "1.5.0",
        "resources": [
            {
                "mode": "managed",
                "type": "aws_s3_bucket",
                "name": "storage",
                "provider": "provider[\"registry.terraform.io/hashicorp/aws\"]",
                "instances": [
                    {
                        "schema_version": 1,
                        "attributes": {
                            "bucket": "my-bucket",
                            "region": "us-east-1"
                        }
                    }
                ]
            }
        ]
    }
    
    metadata = {
        'source': 's3',
        'bucket': 'terraform-states',
        'key': 'prod/terraform.tfstate',
        'last_modified': '2024-01-01T12:00:00Z',
        'size': 2048,
        'collected_at': '2024-01-01T12:00:00Z',
    }
    
    docs = list(parser.parse(tfstate, metadata))
    
    assert len(docs) == 1
    doc = docs[0]
    
    # Check ID format for S3 source
    assert doc['id'] == 'terraform-states/prod/terraform.tfstate/aws_s3_bucket.storage.0'
    
    # Check source metadata
    assert doc['source_type'] == 's3'
    assert doc['source_bucket'] == 'terraform-states'
    assert doc['source_key'] == 'prod/terraform.tfstate'
    assert doc['source_path'] is None
    
    print("✓ Parser S3 test passed!")


async def test_queue():
    """Test memory queue basic operations."""
    print("Testing memory queue...")
    
    queue = MemoryQueue(maxsize=5)
    await queue.start()
    
    # Test empty queue
    assert await queue.empty() is True
    assert await queue.qsize() == 0
    
    # Test put and get
    test_item = {"test": "data", "id": 1}
    await queue.put(test_item)
    
    assert await queue.empty() is False
    assert await queue.qsize() == 1
    
    retrieved_item = await queue.get(timeout=1.0)
    assert retrieved_item == test_item
    
    assert await queue.empty() is True
    assert await queue.qsize() == 0
    
    await queue.stop()
    
    print("✓ Queue test passed!")


async def main():
    """Run all tests."""
    print("Running basic tests for queue-based pipeline components")
    print("=" * 60)
    
    try:
        # Test parser
        test_parser_filesystem()
        test_parser_s3()
        
        # Test queue
        await test_queue()
        
        print("\n" + "=" * 60)
        print("✅ All tests passed!")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())