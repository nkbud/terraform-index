"""Unit tests for tfstate parser."""

import pytest
from datetime import datetime
from indexer.parser.tfstate import TfStateParser


class TestTfStateParser:
    """Test cases for TfStateParser."""

    def test_parse_simple_tfstate(self):
        """Test parsing a simple terraform state file."""
        parser = TfStateParser()
        
        tfstate = {
            "version": 4,
            "terraform_version": "1.5.0",
            "resources": [
                {
                    "type": "aws_instance",
                    "name": "web",
                    "mode": "managed",
                    "provider": "provider[\"registry.terraform.io/hashicorp/aws\"]",
                    "instances": [
                        {
                            "attributes": {
                                "id": "i-1234567890abcdef0",
                                "instance_type": "t3.micro",
                                "tags": {
                                    "Name": "WebServer",
                                    "Environment": "production"
                                }
                            }
                        }
                    ]
                }
            ]
        }
        
        metadata = {
            "bucket": "test-bucket",
            "key": "test/terraform.tfstate",
            "last_modified": "2024-01-01T00:00:00Z"
        }
        
        docs = list(parser.parse(tfstate, metadata))
        
        assert len(docs) == 1
        doc = docs[0]
        
        # Check basic fields
        assert doc["resource_type"] == "aws_instance"
        assert doc["resource_name"] == "web"
        assert doc["resource_mode"] == "managed"
        assert doc["state_version"] == 4
        assert doc["terraform_version"] == "1.5.0"
        
        # Check flattened attributes
        assert doc["attr_id"] == "i-1234567890abcdef0"
        assert doc["attr_instance_type"] == "t3.micro"
        assert doc["attr_tags_Name"] == "WebServer"
        assert doc["attr_tags_Environment"] == "production"
        
        # Check original attributes preserved
        assert doc["attributes"]["id"] == "i-1234567890abcdef0"
        assert doc["attributes"]["tags"]["Name"] == "WebServer"

    def test_flatten_attributes(self):
        """Test attribute flattening."""
        parser = TfStateParser()
        
        nested_obj = {
            "simple": "value",
            "nested": {
                "key1": "value1",
                "key2": {
                    "deep": "deepvalue"
                }
            },
            "list": ["item1", "item2"]
        }
        
        flattened = parser._flatten_attributes(nested_obj, "test_")
        
        assert flattened["test_simple"] == "value"
        assert flattened["test_nested_key1"] == "value1"
        assert flattened["test_nested_key2_deep"] == "deepvalue"
        assert flattened["test_list_0"] == "item1"
        assert flattened["test_list_1"] == "item2"

    def test_parse_multiple_instances(self):
        """Test parsing resource with multiple instances."""
        parser = TfStateParser()
        
        tfstate = {
            "version": 4,
            "terraform_version": "1.5.0",
            "resources": [
                {
                    "type": "aws_instance",
                    "name": "web",
                    "mode": "managed",
                    "provider": "provider[\"registry.terraform.io/hashicorp/aws\"]",
                    "instances": [
                        {"attributes": {"id": "i-1111", "instance_type": "t3.micro"}},
                        {"attributes": {"id": "i-2222", "instance_type": "t3.small"}}
                    ]
                }
            ]
        }
        
        metadata = {
            "bucket": "test-bucket",
            "key": "test/terraform.tfstate",
            "last_modified": "2024-01-01T00:00:00Z"
        }
        
        docs = list(parser.parse(tfstate, metadata))
        
        assert len(docs) == 2
        assert docs[0]["attr_id"] == "i-1111"
        assert docs[1]["attr_id"] == "i-2222"
        assert docs[0]["instance_index"] == 0
        assert docs[1]["instance_index"] == 1