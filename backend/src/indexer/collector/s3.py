"""S3 collector for terraform state files."""

import json
import asyncio
from datetime import datetime
from typing import AsyncIterator, Dict, Any, Set
import boto3
from botocore.exceptions import ClientError, NoCredentialsError

from .base import BaseCollector


class S3Collector(BaseCollector):
    """Collects terraform state files from S3 buckets."""

    def __init__(
        self,
        bucket_name: str,
        prefix: str = "",
        poll_interval: int = 30,
        aws_access_key_id: str = None,
        aws_secret_access_key: str = None,
        endpoint_url: str = None,
    ):
        self.bucket_name = bucket_name
        self.prefix = prefix
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
        self._running = True
        try:
            # Test S3 connection
            await asyncio.get_event_loop().run_in_executor(
                None, self.s3_client.head_bucket, Bucket=self.bucket_name
            )
        except (ClientError, NoCredentialsError) as e:
            raise ConnectionError(f"Failed to connect to S3 bucket {self.bucket_name}: {e}")

    async def stop(self) -> None:
        """Clean up the collector."""
        self._running = False

    async def collect(self) -> AsyncIterator[Dict[str, Any]]:
        """
        Poll S3 bucket for .tfstate files.
        
        Yields:
            Dict with 'content' (parsed tfstate JSON) and 'metadata'
        """
        while self._running:
            try:
                # List objects in bucket
                response = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: self.s3_client.list_objects_v2(
                        Bucket=self.bucket_name,
                        Prefix=self.prefix
                    )
                )
                
                for obj in response.get('Contents', []):
                    key = obj['Key']
                    
                    # Only process .tfstate files
                    if not key.endswith('.tfstate'):
                        continue
                    
                    # Skip if already processed (simple deduplication)
                    object_id = f"{key}:{obj['LastModified'].isoformat()}"
                    if object_id in self.seen_objects:
                        continue
                    
                    try:
                        # Download and parse tfstate file
                        content = await self._download_object(key)
                        tfstate_data = json.loads(content)
                        
                        self.seen_objects.add(object_id)
                        
                        yield {
                            'content': tfstate_data,
                            'metadata': {
                                'source': 's3',
                                'bucket': self.bucket_name,
                                'key': key,
                                'last_modified': obj['LastModified'].isoformat(),
                                'size': obj['Size'],
                                'collected_at': datetime.utcnow().isoformat(),
                            }
                        }
                    except (json.JSONDecodeError, ClientError) as e:
                        print(f"Error processing {key}: {e}")
                        continue
                
            except ClientError as e:
                print(f"Error listing S3 objects: {e}")
            
            # Wait before next poll
            await asyncio.sleep(self.poll_interval)

    async def _download_object(self, key: str) -> str:
        """Download object content from S3."""
        response = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: self.s3_client.get_object(Bucket=self.bucket_name, Key=key)
        )
        return response['Body'].read().decode('utf-8')