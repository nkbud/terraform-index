# terraform-indexer

A queue-based pipeline that collects Terraform `.tfstate` files from multiple sources (local filesystem and S3), parses them, and indexes them into Elasticsearch for exploration and search.

Everything starts with one `docker compose up`.

## Architecture

The system uses a queue-based architecture with three main stages:

```
┌─────────────────┐     Queue 1     ┌──────────────┐     Queue 2     ┌────────────────┐
│   COLLECTORS    │ ─────────────────► │    PARSER    │ ─────────────────► │   UPLOADER     │
│ • Filesystem    │  (raw tfstate)  │ • TfState    │  (parsed docs)  │ • Elasticsearch│
│ • S3 (AWS/Local)│                 │   Parser     │                 │   Bulk API     │
└─────────────────┘                 └──────────────┘                 └────────────────┘
                                                                              │
                                                                       ┌──────▼─────────┐
                                                                       │ OpenSearch /   │
                                                                       │ Elasticsearch  │
                                                                       └────────────────┘
```

**Key Features:**
- **Queue-based processing**: Each stage runs independently with queues between them
- **Multiple sources**: Watches both local filesystem and S3 (real AWS or Localstack)
- **Local developer experience**: Full local setup with Docker Compose
- **Configuration-driven**: Switch between local and cloud modes via `.env` files

## Quick Start

### Option 1: Full Stack (Recommended)

1. **Clone and start everything:**
   ```bash
   git clone https://github.com/nkbud/terraform-index.git
   cd terraform-index
   docker compose up --build
   ```

2. **The system automatically processes:**
   - Sample files in `./tfstates/` directory 
   - Files uploaded to Localstack S3 bucket

3. **Explore your infrastructure:**
   - OpenSearch Dashboards: http://localhost:5601
   - Indexer API: http://localhost:8000
   - API docs: http://localhost:8000/docs

### Option 2: Local Development Setup

For development and testing individual components:

1. **Start infrastructure only:**
   ```bash
   docker compose up opensearch opensearch-dashboards localstack
   ```

2. **Set up Python environment:**
   ```bash
   cd backend
   pip install -e .
   ```

3. **Run components individually:**
   ```bash
   # Test filesystem collector
   python scripts/run_component.py filesystem
   
   # Test S3 collector  
   python scripts/run_component.py s3
   
   # Test parser
   python scripts/run_component.py parser
   
   # Run end-to-end demo
   python scripts/demo.py
   ```

## Features

### Minimal Feature Set (MVP)
- ✅ Poll S3 buckets for new/updated `.tfstate` objects
- ✅ Parse each `.tfstate` resource into flat JSON docs
- ✅ Bulk index to Elasticsearch every N docs/seconds
- ✅ Discoverable UI: OpenSearch Dashboards for instant search

### What Gets Indexed

Each Terraform resource becomes a searchable document with:

- **Resource metadata**: type, name, provider, mode
- **State metadata**: version, terraform version, source location
- **Flattened attributes**: All resource attributes made searchable (e.g., `attr_instance_type`, `attr_tags_Environment`)
- **Original attributes**: Complete nested structure preserved
- **Source tracking**: S3 bucket, key, last modified time

Example indexed document:
```json
{
  "id": "my-bucket/prod/terraform.tfstate/aws_instance.web.0",
  "resource_type": "aws_instance",
  "resource_name": "web",
  "provider": "provider[\"registry.terraform.io/hashicorp/aws\"]",
  "attr_instance_type": "t3.micro",
  "attr_tags_Environment": "production",
  "attr_tags_Name": "WebServer",
  "source_bucket": "my-bucket",
  "source_key": "prod/terraform.tfstate",
  "indexed_at": "2024-01-01T12:00:00Z"
}
```

## Working with Files

### Adding Terraform State Files

**Option 1: Local filesystem (easiest for testing)**
```bash
# Copy your .tfstate files to the watch directory
cp /path/to/your/terraform.tfstate ./tfstates/

# Files are automatically detected and processed
```

**Option 2: Upload to Localstack S3**
```bash
# Seed sample files
python scripts/seed_s3.py

# Or upload your own files
aws --endpoint-url=http://localhost:4566 s3 cp \
  your-terraform.tfstate \
  s3://terraform-states/terraform/your-file.tfstate
```

## Configuration

The system supports two modes configured via `.env` files:

### Local Mode (Default)
```bash
# .env file
MODE=local

# Filesystem watching (local files)
FILESYSTEM_WATCH_DIRECTORY=./tfstates
FILESYSTEM_ENABLED=true

# S3 configuration (localstack)
S3_ENDPOINT_URL=http://localhost:4566
AWS_ACCESS_KEY_ID=test
AWS_SECRET_ACCESS_KEY=test
```

### Cloud Mode
```bash
# .env file  
MODE=cloud

# Disable filesystem watching
FILESYSTEM_ENABLED=false

# Real AWS S3 configuration
S3_ENDPOINT_URL=
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
```

### Complete Configuration Reference

| Variable | Default | Description |
|----------|---------|-------------|
| **Application** | | |
| `MODE` | `local` | Application mode: `local` or `cloud` |
| **S3 Configuration** | | |
| `S3_BUCKET` | `terraform-states` | S3 bucket to poll |
| `S3_PREFIX` | `""` | S3 key prefix filter |
| `S3_POLL_INTERVAL` | `30` | Poll interval in seconds |
| `S3_ENDPOINT_URL` | `None` | Custom S3 endpoint (for LocalStack) |
| `AWS_ACCESS_KEY_ID` | `None` | AWS credentials |
| `AWS_SECRET_ACCESS_KEY` | `None` | AWS credentials |
| **Filesystem Configuration** | | |
| `FILESYSTEM_WATCH_DIRECTORY` | `./tfstates` | Local directory to watch |
| `FILESYSTEM_POLL_INTERVAL` | `5` | Filesystem poll interval in seconds |
| `FILESYSTEM_ENABLED` | `true` | Enable filesystem watching |
| **Elasticsearch Configuration** | | |
| `ES_HOSTS` | `http://localhost:9200` | Elasticsearch hosts |
| `ES_INDEX` | `terraform-resources` | Index name |
| `ES_BATCH_SIZE` | `100` | Bulk indexing batch size |
| `ES_BATCH_TIMEOUT` | `10` | Bulk indexing timeout (seconds) |
| **Queue Configuration** | | |
| `QUEUE_MAX_SIZE` | `1000` | Maximum queue size |

## Features

### Pipeline Architecture
- ✅ **Queue-based processing**: Independent collector, parser, and uploader stages
- ✅ **Multiple sources**: Filesystem and S3 (AWS or Localstack) 
- ✅ **Local development**: Full local setup with sample files
- ✅ **Configuration-driven**: Switch between local/cloud modes

### Data Processing
- ✅ **Terraform state parsing**: Extract individual resources from `.tfstate` files
- ✅ **Flattened attributes**: Make all resource attributes searchable
- ✅ **Source tracking**: Maintain metadata about file origins
- ✅ **Bulk indexing**: Efficient Elasticsearch uploads

### What Gets Indexed

Each Terraform resource becomes a searchable document with:

- **Resource metadata**: type, name, provider, mode
- **State metadata**: version, terraform version, source location  
- **Flattened attributes**: All resource attributes made searchable (e.g., `attr_instance_type`, `attr_tags_Environment`)
- **Original attributes**: Complete nested structure preserved
- **Source tracking**: S3 bucket/filesystem path, last modified time

Example indexed document:
```json
{
  "id": "my-bucket/prod/terraform.tfstate/aws_instance.web.0",
  "resource_type": "aws_instance", 
  "resource_name": "web",
  "provider": "provider[\"registry.terraform.io/hashicorp/aws\"]",
  "attr_instance_type": "t3.micro",
  "attr_tags_Environment": "production", 
  "attr_tags_Name": "WebServer",
  "source_bucket": "my-bucket",
  "source_key": "prod/terraform.tfstate",
  "indexed_at": "2024-01-01T12:00:00Z"
}
```

## Development

### Repository Structure

```
terraform-indexer/
├─ backend/
│  ├─ src/indexer/
│  │   ├─ collector/
│  │   │   ├─ base.py          # Collector ABC
│  │   │   ├─ s3.py            # S3 implementation  
│  │   │   ├─ filesystem.py    # Filesystem collector
│  │   │   └─ composite.py     # Multi-source collector
│  │   ├─ queue/
│  │   │   ├─ base.py          # Queue ABC
│  │   │   └─ memory.py        # In-memory implementation
│  │   ├─ parser/
│  │   │   └─ tfstate.py       # Terraform state parser
│  │   ├─ pipeline.py          # Queue-based worker components
│  │   ├─ es.py                # Elasticsearch client + bulk operations
│  │   └─ main.py              # FastAPI entrypoint
│  ├─ tests/
│  │   ├─ unit/                # Unit tests
│  │   └─ integration/         # Integration tests
│  ├─ Dockerfile
│  └─ pyproject.toml           # Python dependencies
├─ scripts/
│  ├─ seed_s3.py              # Upload sample files to S3
│  ├─ run_component.py        # Test individual components
│  └─ demo.py                 # End-to-end demo
├─ tfstates/                  # Sample .tfstate files
│  ├─ example-web-app.tfstate
│  └─ database-cluster.tfstate
├─ .env                       # Local configuration
├─ docker-compose.yml
└─ README.md
```

### Local Development Setup

1. **Prerequisites:**
   ```bash
   # Install Python 3.11+
   # Install Docker and Docker Compose
   ```

2. **Clone and setup:**
   ```bash
   git clone https://github.com/nkbud/terraform-index.git
   cd terraform-index
   ```

3. **Start infrastructure:**
   ```bash
   # Start OpenSearch and Localstack
   docker compose up opensearch opensearch-dashboards localstack -d
   ```

4. **Setup Python environment:**
   ```bash
   cd backend
   pip install -e .[dev]
   ```

5. **Test individual components:**
   ```bash
   # Test filesystem collector
   python ../scripts/run_component.py filesystem
   
   # Test S3 collector
   python ../scripts/run_component.py s3
   
   # Test parser
   python ../scripts/run_component.py parser
   
   # Test memory queue
   python ../scripts/run_component.py queue
   ```

6. **Run end-to-end demo:**
   ```bash
   python ../scripts/demo.py
   ```

7. **Seed S3 with sample data:**
   ```bash
   python ../scripts/seed_s3.py
   ```

### Running the Application Locally

**Option 1: Run in local mode (filesystem + localstack S3):**
```bash
cd backend/src
export PYTHONPATH=.
export MODE=local
python -m indexer.main
```

**Option 2: Use Docker Compose:**
```bash
docker compose up --build
```

### Testing

```bash
cd backend

# Install dependencies
pip install -e .[dev]

# Run unit tests
pytest tests/unit/ -v

# Run integration tests  
pytest tests/integration/ -v

# Run all tests
pytest -v

# Code formatting
black src/ tests/
isort src/ tests/

# Type checking
mypy src/

# Run simple tests
python ../scripts/test_components.py
```

### Switching Between Local and Cloud Modes

**Local Mode (.env):**
```bash
MODE=local
FILESYSTEM_ENABLED=true
S3_ENDPOINT_URL=http://localhost:4566
AWS_ACCESS_KEY_ID=test
AWS_SECRET_ACCESS_KEY=test
```

**Cloud Mode (.env.cloud):**
```bash
MODE=cloud
FILESYSTEM_ENABLED=false
# S3_ENDPOINT_URL=  # Empty for real AWS
AWS_ACCESS_KEY_ID=your-real-access-key
AWS_SECRET_ACCESS_KEY=your-real-secret-key
```

## API Endpoints

- `GET /` - Health check (shows current mode)
- `GET /stats` - Pipeline statistics including queue sizes and ES status
- `POST /search` - Search terraform resources (Elasticsearch query DSL)

Example API usage:
```bash
# Health check
curl http://localhost:8000/

# Pipeline statistics  
curl http://localhost:8000/stats

# Search for production EC2 instances
curl -X POST http://localhost:8000/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": {
      "bool": {
        "must": [
          {"term": {"resource_type": "aws_instance"}},
          {"term": {"attr_tags_Environment": "production"}}
        ]
      }
    }
  }'
```

## Scripts and Utilities

| Script | Purpose |
|--------|---------|
| `scripts/seed_s3.py` | Upload sample .tfstate files to Localstack S3 |
| `scripts/run_component.py` | Test individual pipeline components |
| `scripts/simple_demo.py` | Filesystem-only pipeline demo |
| `scripts/demo.py` | Full end-to-end pipeline demo |
| `scripts/test_components.py` | Run basic component tests |

## Extensibility

### Adding New Collectors

1. Inherit from `BaseCollector`
2. Implement `collect()`, `start()`, and `stop()` methods
3. Add to `CompositeCollector` in main.py

Example:
```python
class GitCollector(BaseCollector):
    async def collect(self) -> AsyncIterator[Dict[str, Any]]:
        # Implement Git repository scanning
        pass
```

### Adding New Queue Types

1. Inherit from `BaseQueue`  
2. Implement required methods
3. Designed for easy SQS integration:

```python
class SQSQueue(BaseQueue):
    def __init__(self, queue_url: str):
        self.sqs = boto3.client('sqs')
        self.queue_url = queue_url
    
    async def put(self, item: Dict[str, Any]) -> None:
        # Send to SQS
        pass
```

## Monitoring

- **Queue Sizes**: Monitor via `/stats` endpoint
- **Processing Rate**: Track documents per second
- **Error Handling**: All workers continue on individual file errors
- **Resource Usage**: Each stage runs independently for scalability

## Architecture Benefits

1. **Decoupled Processing**: Each stage (collect → parse → upload) runs independently
2. **Scalability**: Easy to scale individual components or add more workers
3. **Reliability**: Queues provide buffering during load spikes or temporary failures
4. **Testability**: Individual components can be tested and run separately
5. **Flexibility**: Support multiple input sources and easy to add new ones

## Performance Tuning

- **Queue Size**: Adjust `QUEUE_MAX_SIZE` based on memory constraints
- **Poll Intervals**: Tune collector poll intervals for your data freshness needs
- **ES Batch Size**: Optimize `ES_BATCH_SIZE` for your Elasticsearch cluster
- **Concurrent Workers**: Multiple parser/uploader workers can be added for higher throughput

## Extensibility

### Adding New Collectors

Implement the `BaseCollector` interface:

```python
from indexer.collector.base import BaseCollector

class MyCollector(BaseCollector):
    async def collect(self):
        # Yield {"content": tfstate_dict, "metadata": source_info}
        pass
    
    async def start(self):
        # Initialize collector
        pass
    
    async def stop(self):
        # Cleanup
        pass
```

## Troubleshooting

**No documents being processed:**
- Check pipeline status: `curl http://localhost:8000/stats`
- Verify .tfstate files exist in `./tfstates/` directory
- Check container logs: `docker compose logs -f terraform-indexer`
- Ensure Elasticsearch is healthy: `curl http://localhost:9200/_cluster/health`

**Connection errors:**
- Verify all services are running: `docker compose ps`
- Check service logs: `docker compose logs [service-name]`
- For S3 issues, ensure Localstack is running: `curl http://localhost:4566/health`

**Performance issues:**
- Monitor queue sizes via `/stats` endpoint
- Adjust `QUEUE_MAX_SIZE` for memory constraints
- Tune `ES_BATCH_SIZE` and `ES_BATCH_TIMEOUT` for your Elasticsearch cluster
- Increase poll intervals if processing very large state files

**Local development issues:**
- Ensure correct Python path: `export PYTHONPATH=./backend/src:$PYTHONPATH`
- Test individual components: `python scripts/run_component.py queue`
- Run filesystem-only demo: `python scripts/simple_demo.py`

**Mode switching problems:**
- Verify `.env` file configuration matches desired mode
- Check that `FILESYSTEM_ENABLED` is set correctly for your mode
- Ensure AWS credentials are properly configured for cloud mode