"""S3 collector for terraform state files."""

import json
import asyncio
from datetime import datetime
from typing import AsyncIterator, Dict, Any, Set
import boto3
from botocore.exceptions import ClientError, NoCredentialsError

from .base import BaseCollector
from ..logging import LoggingMixin


class S3Collector(BaseCollector, LoggingMixin):
    """Collects terraform state files from S3 buckets."""

    def __init__(
        self,
        bucket_names,  # Can be list or string (comma-separated)
        poll_interval: int = 30,
        aws_access_key_id: str = None,
        aws_secret_access_key: str = None,
        endpoint_url: str = None,
    ):
        # Parse bucket names - handle both list and comma-separated string
        if isinstance(bucket_names, str):
            self.bucket_names = [name.strip() for name in bucket_names.split(',') if name.strip()]
        elif isinstance(bucket_names, list):
            self.bucket_names = bucket_names
        else:
            raise ValueError(f"bucket_names must be a string or list, got {type(bucket_names)}")
            
        self.poll_interval = poll_interval
        self.seen_objects: Set[str] = set()
        self._running = False
        
        # S3 client configuration
        session = boto3.Session(
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
        )
        self.s3_client = session.client('s3', endpoint_url=endpoint_url)

    async def start(self) -> None:
        """Initialize the collector."""
        self.logger.info(f"☁️ Starting S3 collector (buckets: {self.bucket_names})")
        self._running = True
        
        # Test S3 connection for all buckets
        for bucket_name in self.bucket_names:
            try:
                self.logger.debug(f"Testing connection to bucket: {bucket_name}")
                await asyncio.get_event_loop().run_in_executor(
                    None, lambda b=bucket_name: self.s3_client.head_bucket(Bucket=b)
                )
                self.logger.debug(f"✅ Connected to bucket: {bucket_name}")
            except (ClientError, NoCredentialsError) as e:
                self.logger.error(f"❌ Failed to connect to S3 bucket {bucket_name}: {e}")
                raise ConnectionError(f"Failed to connect to S3 bucket {bucket_name}: {e}")

    async def stop(self) -> None:
        """Clean up the collector."""
        self.logger.info("🛑 Stopping S3 collector")
        self._running = False

    async def collect(self) -> AsyncIterator[Dict[str, Any]]:
        """
        Poll S3 buckets for .tfstate files.
        
        Yields:
            Dict with 'content' (parsed tfstate JSON) and 'metadata'
        """
        self.logger.debug(f"Starting S3 collection loop (poll interval: {self.poll_interval}s)")
        
        while self._running:
            try:
                # Process all buckets
                total_objects_found = 0
                
                for bucket_name in self.bucket_names:
                    self.logger.debug(f"Scanning bucket: {bucket_name}")
                    
                    # List objects in bucket (search entire bucket for *.tfstate files)
                    response = await asyncio.get_event_loop().run_in_executor(
                        None,
                        lambda: self.s3_client.list_objects_v2(
                            Bucket=bucket_name
                        )
                    )
                    
                    objects_in_bucket = 0
                    for obj in response.get('Contents', []):
                        key = obj['Key']
                        
                        # Only process .tfstate files
                        if not key.endswith('.tfstate'):
                            continue
                        
                        # Skip if already processed (simple deduplication)
                        object_id = f"{bucket_name}:{key}:{obj['LastModified'].isoformat()}"
                        if object_id in self.seen_objects:
                            continue
                        
                        try:
                            self.logger.debug(f"Processing new/updated S3 object: s3://{bucket_name}/{key}")
                            
                            # Download and parse tfstate file
                            content = await self._download_object(bucket_name, key)
                            tfstate_data = json.loads(content)
                            
                            self.seen_objects.add(object_id)
                            objects_in_bucket += 1
                            total_objects_found += 1
                            
                            file_size_kb = len(content) / 1024
                            self.logger.debug(f"Downloaded {file_size_kb:.1f}KB from s3://{bucket_name}/{key}")
                            
                            yield {
                                'content': tfstate_data,
                                'metadata': {
                                    'source': f's3://{bucket_name}/{key}',
                                    'type': 's3',
                                    'bucket': bucket_name,
                                    'key': key,
                                    'last_modified': obj['LastModified'].isoformat(),
                                    'size_bytes': obj['Size'],
                                    'collected_at': datetime.now().isoformat(),
                                }
                            }
                        except (json.JSONDecodeError, ClientError) as e:
                            self.logger.error(f"❌ Error processing s3://{bucket_name}/{key}: {e}")
                            continue
                    
                    if objects_in_bucket > 0:
                        self.logger.debug(f"Found {objects_in_bucket} new/updated objects in bucket {bucket_name}")
                
                if total_objects_found > 0:
                    self.logger.info(f"☁️ Processed {total_objects_found} S3 objects")
                
            except ClientError as e:
                self.logger.error(f"❌ Error listing S3 objects: {e}")
            except Exception as e:
                self.logger.error(f"❌ Unexpected error in S3 collector: {e}")
                self.logger.exception("Full error details:")
            
            # Wait before next poll
            await asyncio.sleep(self.poll_interval)

    async def _download_object(self, bucket_name: str, key: str) -> str:
        """Download object content from S3."""
        response = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: self.s3_client.get_object(Bucket=bucket_name, Key=key)
        )
        return response['Body'].read().decode('utf-8')