"""Integration tests for the full terraform-indexer stack."""

import pytest
import asyncio
import json
import boto3
from moto import mock_s3

from indexer.collector.s3 import S3Collector
from indexer.parser.tfstate import TfStateParser


@mock_s3
class TestS3Integration:
    """Integration tests using mocked S3."""

    @pytest.fixture
    def s3_setup(self):
        """Set up mocked S3 bucket with test data."""
        # Create mock S3 bucket
        s3_client = boto3.client(
            "s3",
            region_name="us-east-1",
            aws_access_key_id="testing",
            aws_secret_access_key="testing",
        )
        
        bucket_name = "test-terraform-bucket"
        s3_client.create_bucket(Bucket=bucket_name)
        
        # Upload test tfstate file
        tfstate_content = {
            "version": 4,
            "terraform_version": "1.5.0",
            "resources": [
                {
                    "type": "aws_instance",
                    "name": "web_server",
                    "mode": "managed",
                    "provider": "provider[\"registry.terraform.io/hashicorp/aws\"]",
                    "instances": [
                        {
                            "attributes": {
                                "id": "i-1234567890abcdef0",
                                "instance_type": "t3.micro",
                                "availability_zone": "us-west-2a",
                                "tags": {
                                    "Name": "WebServer",
                                    "Environment": "production",
                                    "Team": "platform"
                                },
                                "vpc_security_group_ids": ["sg-12345678"],
                                "subnet_id": "subnet-12345678"
                            }
                        }
                    ]
                },
                {
                    "type": "aws_s3_bucket",
                    "name": "app_bucket",
                    "mode": "managed",
                    "provider": "provider[\"registry.terraform.io/hashicorp/aws\"]",
                    "instances": [
                        {
                            "attributes": {
                                "id": "my-app-bucket-prod",
                                "bucket": "my-app-bucket-prod",
                                "region": "us-west-2",
                                "tags": {
                                    "Environment": "production",
                                    "Purpose": "application-data"
                                }
                            }
                        }
                    ]
                }
            ]
        }
        
        s3_client.put_object(
            Bucket=bucket_name,
            Key="environments/prod/terraform.tfstate",
            Body=json.dumps(tfstate_content)
        )
        
        return bucket_name, s3_client

    @pytest.mark.asyncio
    async def test_end_to_end_collection_and_parsing(self, s3_setup):
        """Test full flow from S3 collection to parsed documents."""
        bucket_name, s3_client = s3_setup
        
        # Create collector
        collector = S3Collector(
            bucket_names=bucket_name,
            poll_interval=1,
            aws_access_key_id="testing",
            aws_secret_access_key="testing",
        )
        
        # Override S3 client with mocked one
        collector.s3_client = s3_client
        
        # Create parser
        parser = TfStateParser()
        
        try:
            await collector.start()
            
            # Collect and parse documents
            documents = []
            async for state_data in collector.collect():
                tfstate = state_data['content']
                metadata = state_data['metadata']
                
                # Parse into individual resource documents
                for doc in parser.parse(tfstate, metadata):
                    documents.append(doc)
                
                # Break after first collection
                break
            
            # Verify we got the expected documents
            assert len(documents) == 2  # aws_instance + aws_s3_bucket
            
            # Check instance document
            instance_doc = next(d for d in documents if d['resource_type'] == 'aws_instance')
            assert instance_doc['resource_name'] == 'web_server'
            assert instance_doc['attr_instance_type'] == 't3.micro'
            assert instance_doc['attr_tags_Environment'] == 'production'
            assert instance_doc['attr_tags_Name'] == 'WebServer'
            assert instance_doc['source_bucket'] == bucket_name
            assert instance_doc['source_key'] == 'environments/prod/terraform.tfstate'
            
            # Check S3 bucket document
            bucket_doc = next(d for d in documents if d['resource_type'] == 'aws_s3_bucket')
            assert bucket_doc['resource_name'] == 'app_bucket'
            assert bucket_doc['attr_bucket'] == 'my-app-bucket-prod'
            assert bucket_doc['attr_region'] == 'us-west-2'
            assert bucket_doc['attr_tags_Purpose'] == 'application-data'
            
            # Verify both documents have proper metadata
            for doc in documents:
                assert 'indexed_at' in doc
                assert 'id' in doc
                assert doc['state_version'] == 4
                assert doc['terraform_version'] == '1.5.0'
                
        finally:
            await collector.stop()

    @pytest.mark.asyncio 
    async def test_multiple_tfstate_files(self, s3_setup):
        """Test processing multiple tfstate files."""
        bucket_name, s3_client = s3_setup
        
        # Add another tfstate file
        tfstate_content_2 = {
            "version": 4,
            "terraform_version": "1.5.0",
            "resources": [
                {
                    "type": "aws_rds_instance",
                    "name": "database",
                    "mode": "managed",
                    "provider": "provider[\"registry.terraform.io/hashicorp/aws\"]",
                    "instances": [
                        {
                            "attributes": {
                                "id": "prod-db-instance",
                                "engine": "postgres",
                                "engine_version": "14.9",
                                "instance_class": "db.t3.micro"
                            }
                        }
                    ]
                }
            ]
        }
        
        s3_client.put_object(
            Bucket=bucket_name,
            Key="environments/staging/terraform.tfstate",
            Body=json.dumps(tfstate_content_2)
        )
        
        collector = S3Collector(
            bucket_names=bucket_name,
            poll_interval=1,
            aws_access_key_id="testing",
            aws_secret_access_key="testing",
        )
        collector.s3_client = s3_client
        
        parser = TfStateParser()
        
        try:
            await collector.start()
            
            all_documents = []
            collection_count = 0
            
            async for state_data in collector.collect():
                for doc in parser.parse(state_data['content'], state_data['metadata']):
                    all_documents.append(doc)
                
                collection_count += 1
                if collection_count >= 2:  # Process both files
                    break
            
            # Should have 3 total documents: 2 from prod + 1 from staging
            assert len(all_documents) == 3
            
            # Check we have the expected resource types
            resource_types = {doc['resource_type'] for doc in all_documents}
            assert resource_types == {'aws_instance', 'aws_s3_bucket', 'aws_rds_instance'}
            
            # Check RDS document from staging
            rds_doc = next(d for d in all_documents if d['resource_type'] == 'aws_rds_instance')
            assert rds_doc['attr_engine'] == 'postgres'
            assert rds_doc['source_key'] == 'environments/staging/terraform.tfstate'
            
        finally:
            await collector.stop()