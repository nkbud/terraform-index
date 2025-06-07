"""AWS SQS queue implementation for terraform-indexer."""

import asyncio
import json
from typing import Any, Dict, Optional

import boto3
from botocore.exceptions import ClientError

from .base import BaseQueue


class SQSQueue(BaseQueue):
    """AWS SQS queue implementation."""

    def __init__(
        self,
        queue_url: str,
        aws_access_key_id: str = None,
        aws_secret_access_key: str = None,
        region_name: str = "us-east-1",
        endpoint_url: str = None,
        visibility_timeout: int = 30,
        message_retention_period: int = 1209600,  # 14 days
    ):
        """
        Initialize the SQS queue.
        
        Args:
            queue_url: SQS queue URL
            aws_access_key_id: AWS access key ID
            aws_secret_access_key: AWS secret access key
            region_name: AWS region name
            endpoint_url: Custom endpoint URL (e.g., for Localstack)
            visibility_timeout: Message visibility timeout in seconds
            message_retention_period: Message retention period in seconds
        """
        self.queue_url = queue_url
        self.visibility_timeout = visibility_timeout
        self.message_retention_period = message_retention_period
        self._client: Optional[boto3.client] = None
        
        # SQS client configuration
        session = boto3.Session(
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            region_name=region_name,
        )
        
        self.sqs_client = session.client('sqs', endpoint_url=endpoint_url)

    async def start(self) -> None:
        """Initialize the queue."""
        # Test connection by getting queue attributes
        try:
            await asyncio.get_event_loop().run_in_executor(
                None, 
                lambda: self.sqs_client.get_queue_attributes(
                    QueueUrl=self.queue_url,
                    AttributeNames=['QueueArn']
                )
            )
        except ClientError as e:
            raise ConnectionError(f"Failed to connect to SQS queue {self.queue_url}: {e}")

    async def stop(self) -> None:
        """Clean up the queue."""
        # Nothing to clean up for SQS
        pass

    async def put(self, item: Dict[str, Any]) -> None:
        """Put an item into the queue."""
        try:
            message_body = json.dumps(item)
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.sqs_client.send_message(
                    QueueUrl=self.queue_url,
                    MessageBody=message_body
                )
            )
        except ClientError as e:
            raise RuntimeError(f"Failed to send message to SQS: {e}")

    async def get(self, timeout: Optional[float] = None) -> Dict[str, Any]:
        """Get an item from the queue."""
        try:
            # Calculate wait time for long polling
            wait_time_seconds = min(int(timeout) if timeout else 20, 20)
            
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.sqs_client.receive_message(
                    QueueUrl=self.queue_url,
                    MaxNumberOfMessages=1,
                    WaitTimeSeconds=wait_time_seconds,
                    VisibilityTimeout=self.visibility_timeout
                )
            )
            
            messages = response.get('Messages', [])
            if not messages:
                if timeout is not None:
                    raise asyncio.TimeoutError("No messages received within timeout")
                # If no timeout specified, return empty result
                return {}
            
            message = messages[0]
            receipt_handle = message['ReceiptHandle']
            message_body = json.loads(message['Body'])
            
            # Delete the message after successful processing
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.sqs_client.delete_message(
                    QueueUrl=self.queue_url,
                    ReceiptHandle=receipt_handle
                )
            )
            
            return message_body
            
        except ClientError as e:
            raise RuntimeError(f"Failed to receive message from SQS: {e}")
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Failed to decode message body: {e}")

    async def empty(self) -> bool:
        """Return True if the queue is empty."""
        try:
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.sqs_client.get_queue_attributes(
                    QueueUrl=self.queue_url,
                    AttributeNames=['ApproximateNumberOfMessages']
                )
            )
            
            approximate_count = int(response['Attributes']['ApproximateNumberOfMessages'])
            return approximate_count == 0
            
        except ClientError as e:
            # If we can't get attributes, assume not empty to be safe
            return False

    async def qsize(self) -> int:
        """Return the approximate size of the queue."""
        try:
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.sqs_client.get_queue_attributes(
                    QueueUrl=self.queue_url,
                    AttributeNames=['ApproximateNumberOfMessages']
                )
            )
            
            return int(response['Attributes']['ApproximateNumberOfMessages'])
            
        except ClientError as e:
            # If we can't get attributes, return 0
            return 0