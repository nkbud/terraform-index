#!/bin/bash
# Setup script for terraform-indexer demo

set -e

echo "Setting up terraform-indexer demo..."

# Wait for LocalStack to be ready
echo "Waiting for LocalStack to be ready..."
until curl -s http://localhost:4566/health | grep -q "running"; do
  echo "LocalStack not ready yet, waiting..."
  sleep 2
done

echo "LocalStack is ready!"

# Create S3 bucket
echo "Creating S3 bucket..."
aws --endpoint-url=http://localhost:4566 s3 mb s3://terraform-states

# Upload sample terraform state
echo "Uploading sample terraform state..."
aws --endpoint-url=http://localhost:4566 s3 cp \
  /app/examples/sample-terraform.tfstate \
  s3://terraform-states/prod/infrastructure/terraform.tfstate

echo "Demo setup complete!"
echo "- S3 bucket: terraform-states"
echo "- Sample state file uploaded to: prod/infrastructure/terraform.tfstate"
echo "- Access OpenSearch Dashboards at: http://localhost:5601"
echo "- Access indexer API at: http://localhost:8000"