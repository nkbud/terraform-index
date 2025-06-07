"""Unit tests for S3 collector."""

import pytest
from unittest.mock import Mock, AsyncMock, patch
import json
from datetime import datetime

from indexer.collector.s3 import S3Collector


class TestS3Collector:
    """Test cases for S3Collector."""

    @pytest.fixture
    def mock_s3_client(self):
        """Mock S3 client."""
        client = Mock()
        client.head_bucket = Mock()
        client.list_objects_v2 = Mock()
        client.get_object = Mock()
        return client

    @pytest.fixture
    def collector(self, mock_s3_client):
        """Create S3Collector with mocked client."""
        collector = S3Collector(
            bucket_names="test-bucket",
            poll_interval=1
        )
        collector.s3_client = mock_s3_client
        return collector

    @pytest.mark.asyncio
    async def test_start_success(self, collector, mock_s3_client):
        """Test successful collector start."""
        mock_s3_client.head_bucket.return_value = None
        
        await collector.start()
        
        assert collector._running is True
        mock_s3_client.head_bucket.assert_called_once_with(Bucket="test-bucket")

    @pytest.mark.asyncio
    async def test_start_connection_error(self, collector, mock_s3_client):
        """Test collector start with connection error."""
        from botocore.exceptions import ClientError
        
        mock_s3_client.head_bucket.side_effect = ClientError(
            {"Error": {"Code": "NoSuchBucket"}}, "head_bucket"
        )
        
        with pytest.raises(ConnectionError):
            await collector.start()

    @pytest.mark.asyncio
    async def test_collect_tfstate_files(self, collector, mock_s3_client):
        """Test collecting tfstate files."""
        # Mock S3 responses
        mock_s3_client.list_objects_v2.return_value = {
            "Contents": [
                {
                    "Key": "terraform/prod.tfstate",
                    "LastModified": datetime(2024, 1, 1, 12, 0, 0),
                    "Size": 1024
                },
                {
                    "Key": "terraform/dev.tfstate", 
                    "LastModified": datetime(2024, 1, 1, 13, 0, 0),
                    "Size": 512
                },
                {
                    "Key": "terraform/other.txt",  # Should be ignored
                    "LastModified": datetime(2024, 1, 1, 14, 0, 0),
                    "Size": 100
                }
            ]
        }
        
        # Mock tfstate content
        tfstate_content = {
            "version": 4,
            "terraform_version": "1.5.0",
            "resources": []
        }
        
        mock_s3_client.get_object.return_value = {
            "Body": Mock(read=Mock(return_value=json.dumps(tfstate_content).encode()))
        }
        
        collector._running = True
        
        # Collect one iteration
        collected = []
        count = 0
        async for item in collector.collect():
            collected.append(item)
            count += 1
            if count >= 2:  # Expect 2 tfstate files
                collector._running = False
                break
        
        assert len(collected) == 2
        
        # Check first collected item
        item1 = collected[0]
        assert item1["content"] == tfstate_content
        assert item1["metadata"]["bucket"] == "test-bucket"
        assert item1["metadata"]["key"] == "terraform/prod.tfstate"
        assert item1["metadata"]["source"] == "s3"
        
        # Verify S3 client calls
        mock_s3_client.list_objects_v2.assert_called_with(
            Bucket="test-bucket"
        )
        assert mock_s3_client.get_object.call_count == 2

    @pytest.mark.asyncio
    async def test_deduplication(self, collector, mock_s3_client):
        """Test that duplicate objects are not processed twice."""
        last_modified = datetime(2024, 1, 1, 12, 0, 0)
        
        mock_s3_client.list_objects_v2.return_value = {
            "Contents": [
                {
                    "Key": "terraform/test.tfstate",
                    "LastModified": last_modified,
                    "Size": 1024
                }
            ]
        }
        
        tfstate_content = {"version": 4, "resources": []}
        mock_s3_client.get_object.return_value = {
            "Body": Mock(read=Mock(return_value=json.dumps(tfstate_content).encode()))
        }
        
        collector._running = True
        
        # First collection should yield the file
        collected = []
        count = 0
        async for item in collector.collect():
            collected.append(item)
            count += 1
            if count >= 1:
                break
        
        assert len(collected) == 1
        
        # Second collection should not yield the same file again
        collected2 = []
        count = 0
        async for item in collector.collect():
            collected2.append(item)
            count += 1
            if count >= 1:  # Give it a chance to yield
                collector._running = False
                break
        
        # Should not collect the same file again
        assert len(collected2) == 0