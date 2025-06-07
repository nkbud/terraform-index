#!/usr/bin/env python3
"""Script to seed sample .tfstate files to localstack S3 bucket."""

import os
import sys
import boto3
from pathlib import Path

def seed_s3_bucket():
    """Upload sample .tfstate files to localstack S3."""
    
    # Configuration
    endpoint_url = os.getenv("S3_ENDPOINT_URL", "http://localhost:4566")
    bucket_name = os.getenv("S3_BUCKET", "terraform-states")
    aws_access_key_id = os.getenv("AWS_ACCESS_KEY_ID", "test")
    aws_secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY", "test")
    
    # Initialize S3 client
    s3_client = boto3.client(
        's3',
        endpoint_url=endpoint_url,
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
    )
    
    # Create bucket if it doesn't exist
    try:
        s3_client.head_bucket(Bucket=bucket_name)
        print(f"Bucket {bucket_name} already exists")
    except:
        try:
            s3_client.create_bucket(Bucket=bucket_name)
            print(f"Created bucket {bucket_name}")
        except Exception as e:
            print(f"Error creating bucket: {e}")
            return False
    
    # Find and upload .tfstate files
    tfstates_dir = Path("./tfstates")
    if not tfstates_dir.exists():
        print(f"Directory {tfstates_dir} does not exist")
        return False
    
    uploaded_count = 0
    for tfstate_file in tfstates_dir.glob("*.tfstate"):
        try:
            key = f"terraform/{tfstate_file.name}"
            s3_client.upload_file(str(tfstate_file), bucket_name, key)
            print(f"Uploaded {tfstate_file.name} to s3://{bucket_name}/{key}")
            uploaded_count += 1
        except Exception as e:
            print(f"Error uploading {tfstate_file.name}: {e}")
    
    print(f"Successfully uploaded {uploaded_count} files to S3")
    return True

if __name__ == "__main__":
    print("Seeding localstack S3 bucket with sample .tfstate files...")
    success = seed_s3_bucket()
    sys.exit(0 if success else 1)