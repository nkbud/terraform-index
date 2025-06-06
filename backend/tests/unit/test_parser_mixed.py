"""Tests for parser with mixed source types."""

import pytest
from datetime import datetime

from indexer.parser.tfstate import TfStateParser


def test_parser_with_filesystem_metadata():
    """Test parser with filesystem source metadata."""
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


def test_parser_with_s3_metadata():
    """Test parser with S3 source metadata."""
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
    
    # Check resource metadata
    assert doc['resource_type'] == 'aws_s3_bucket'
    assert doc['resource_name'] == 'storage'
    
    # Check flattened attributes
    assert doc['attr_bucket'] == 'my-bucket'
    assert doc['attr_region'] == 'us-east-1'


def test_parser_with_multiple_instances():
    """Test parser with resource having multiple instances."""
    parser = TfStateParser()
    
    tfstate = {
        "version": 4,
        "terraform_version": "1.5.0",
        "resources": [
            {
                "mode": "managed",
                "type": "aws_instance",
                "name": "workers",
                "provider": "provider[\"registry.terraform.io/hashicorp/aws\"]",
                "instances": [
                    {
                        "schema_version": 1,
                        "attributes": {
                            "id": "i-worker1",
                            "instance_type": "t3.micro"
                        }
                    },
                    {
                        "schema_version": 1,
                        "attributes": {
                            "id": "i-worker2",
                            "instance_type": "t3.small"
                        }
                    }
                ]
            }
        ]
    }
    
    metadata = {
        'source': 'filesystem',
        'path': '/path/to/workers.tfstate',
        'collected_at': '2024-01-01T12:00:00Z',
    }
    
    docs = list(parser.parse(tfstate, metadata))
    
    assert len(docs) == 2
    
    # Check first instance
    doc1 = docs[0]
    assert doc1['id'] == '/path/to/workers.tfstate/aws_instance.workers.0'
    assert doc1['instance_index'] == 0
    assert doc1['attr_id'] == 'i-worker1'
    assert doc1['attr_instance_type'] == 't3.micro'
    
    # Check second instance
    doc2 = docs[1]
    assert doc2['id'] == '/path/to/workers.tfstate/aws_instance.workers.1'
    assert doc2['instance_index'] == 1
    assert doc2['attr_id'] == 'i-worker2'
    assert doc2['attr_instance_type'] == 't3.small'


def test_parser_with_missing_metadata():
    """Test parser gracefully handles missing metadata fields."""
    parser = TfStateParser()
    
    tfstate = {
        "version": 4,
        "resources": [
            {
                "mode": "managed",
                "type": "aws_instance",
                "name": "test",
                "instances": [{"attributes": {"id": "i-test"}}]
            }
        ]
    }
    
    # Minimal metadata
    metadata = {
        'source': 'unknown',
        'collected_at': '2024-01-01T12:00:00Z',
    }
    
    docs = list(parser.parse(tfstate, metadata))
    
    assert len(docs) == 1
    doc = docs[0]
    
    # Should handle unknown source gracefully
    assert doc['source_type'] == 'unknown'
    assert doc['source_bucket'] is None
    assert doc['source_key'] is None
    assert doc['source_path'] is None