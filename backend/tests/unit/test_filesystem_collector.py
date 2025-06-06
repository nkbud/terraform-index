"""Tests for filesystem collector."""

import pytest
import asyncio
import json
import tempfile
import shutil
from pathlib import Path

from indexer.collector.filesystem import FileSystemCollector


@pytest.mark.asyncio
async def test_filesystem_collector_basic():
    """Test basic filesystem collector functionality."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create test .tfstate file
        test_file = Path(temp_dir) / "test.tfstate"
        test_data = {
            "version": 4,
            "terraform_version": "1.5.0",
            "resources": [
                {
                    "mode": "managed",
                    "type": "aws_instance",
                    "name": "test",
                    "provider": "provider[\"registry.terraform.io/hashicorp/aws\"]",
                    "instances": [
                        {
                            "schema_version": 1,
                            "attributes": {
                                "id": "i-12345",
                                "instance_type": "t3.micro"
                            }
                        }
                    ]
                }
            ]
        }
        
        test_file.write_text(json.dumps(test_data))
        
        # Create collector
        collector = FileSystemCollector(
            watch_directory=temp_dir,
            poll_interval=1,
        )
        
        await collector.start()
        
        # Collect items
        collected_items = []
        async for item in collector.collect():
            collected_items.append(item)
            if len(collected_items) >= 1:
                break  # Stop after collecting one item
        
        await collector.stop()
        
        # Verify collected item
        assert len(collected_items) == 1
        item = collected_items[0]
        
        assert item['content'] == test_data
        assert item['metadata']['source'] == 'filesystem'
        assert item['metadata']['path'] == str(test_file)
        assert 'last_modified' in item['metadata']
        assert 'collected_at' in item['metadata']


@pytest.mark.asyncio
async def test_filesystem_collector_deduplication():
    """Test that files are not processed multiple times."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create test .tfstate file
        test_file = Path(temp_dir) / "test.tfstate"
        test_data = {"version": 4, "resources": []}
        test_file.write_text(json.dumps(test_data))
        
        # Create collector
        collector = FileSystemCollector(
            watch_directory=temp_dir,
            poll_interval=0.5,
        )
        
        await collector.start()
        
        # Collect items for a short time
        collected_items = []
        start_time = asyncio.get_event_loop().time()
        
        async for item in collector.collect():
            collected_items.append(item)
            
            # Stop after 2 seconds to allow multiple poll cycles
            if asyncio.get_event_loop().time() - start_time > 2:
                break
        
        await collector.stop()
        
        # Should only collect the file once despite multiple poll cycles
        assert len(collected_items) == 1


@pytest.mark.asyncio
async def test_filesystem_collector_multiple_files():
    """Test collector with multiple .tfstate files."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create multiple test files
        test_data = {"version": 4, "resources": []}
        
        for i in range(3):
            test_file = Path(temp_dir) / f"test-{i}.tfstate"
            test_file.write_text(json.dumps(test_data))
        
        # Create non-.tfstate file (should be ignored)
        non_tfstate = Path(temp_dir) / "not-terraform.json"
        non_tfstate.write_text(json.dumps(test_data))
        
        # Create collector
        collector = FileSystemCollector(
            watch_directory=temp_dir,
            poll_interval=1,
        )
        
        await collector.start()
        
        # Collect items
        collected_items = []
        async for item in collector.collect():
            collected_items.append(item)
            if len(collected_items) >= 3:
                break
        
        await collector.stop()
        
        # Should collect exactly 3 .tfstate files
        assert len(collected_items) == 3
        
        # Verify all are .tfstate files
        for item in collected_items:
            assert item['metadata']['path'].endswith('.tfstate')


@pytest.mark.asyncio
async def test_filesystem_collector_recursive():
    """Test recursive directory scanning."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create nested directory structure
        subdir = Path(temp_dir) / "subdir"
        subdir.mkdir()
        
        # Create .tfstate files in both root and subdir
        test_data = {"version": 4, "resources": []}
        
        root_file = Path(temp_dir) / "root.tfstate"
        root_file.write_text(json.dumps(test_data))
        
        sub_file = subdir / "sub.tfstate"
        sub_file.write_text(json.dumps(test_data))
        
        # Create collector with recursive=True (default)
        collector = FileSystemCollector(
            watch_directory=temp_dir,
            poll_interval=1,
            recursive=True,
        )
        
        await collector.start()
        
        # Collect items
        collected_items = []
        async for item in collector.collect():
            collected_items.append(item)
            if len(collected_items) >= 2:
                break
        
        await collector.stop()
        
        # Should collect both files
        assert len(collected_items) == 2
        
        paths = [item['metadata']['path'] for item in collected_items]
        assert str(root_file) in paths
        assert str(sub_file) in paths