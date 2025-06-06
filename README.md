# terraform-indexer

A simple, fully-local stack that collects Terraform `.tfstate` files from S3, indexes them into Elasticsearch, and provides an off-the-shelf UI for exploration.

Everything starts with one `docker compose up`.

## Architecture

```
┌────────────────┐      tfstate JSON      ┌────────────────┐     REST / UI queries
│  S3 Bucket(s)  │ ──────────────────────►│  Backend (Py)  │ ───► OpenSearch Dashboards
└────────────────┘   (poll every X sec)   │  • S3 Collector│     (direct‐to‐ES queries)
                                          │  • Parser      │
                                          │  • ES Bulk API │
                                          └──────▲─────────┘
                                                9200
                                           ┌────────────┐
                                           │OpenSearch /│
                                           │Elasticsearch│
                                           └────────────┘
```

## Quick Start

1. **Clone and start the stack:**
   ```bash
   git clone https://github.com/nkbud/terraform-index.git
   cd terraform-index
   docker compose up --build
   ```

2. **Upload a terraform state file** (optional - there's a sample included):
   ```bash
   # Using the provided demo setup
   docker exec terraform-indexer bash /app/examples/setup-demo.sh
   
   # Or manually upload your own tfstate file
   aws --endpoint-url=http://localhost:4566 s3 cp \
     your-terraform.tfstate \
     s3://terraform-states/your-path/terraform.tfstate
   ```

3. **Explore your infrastructure:**
   - OpenSearch Dashboards: http://localhost:5601
   - Indexer API: http://localhost:8000
   - API docs: http://localhost:8000/docs

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

## Configuration

Environment variables for the backend service:

| Variable | Default | Description |
|----------|---------|-------------|
| `S3_BUCKET` | `terraform-states` | S3 bucket to poll |
| `S3_PREFIX` | `""` | S3 key prefix filter |
| `S3_POLL_INTERVAL` | `30` | Poll interval in seconds |
| `S3_ENDPOINT_URL` | `None` | Custom S3 endpoint (for LocalStack) |
| `AWS_ACCESS_KEY_ID` | `None` | AWS credentials |
| `AWS_SECRET_ACCESS_KEY` | `None` | AWS credentials |
| `ES_HOSTS` | `http://localhost:9200` | Elasticsearch hosts |
| `ES_INDEX` | `terraform-resources` | Index name |
| `ES_BATCH_SIZE` | `100` | Bulk indexing batch size |
| `ES_BATCH_TIMEOUT` | `10` | Bulk indexing timeout (seconds) |

## Development

### Repository Structure

```
terraform-indexer/
├─ backend/
│  ├─ src/indexer/
│  │   ├─ collector/
│  │   │   ├─ base.py          # Collector ABC
│  │   │   └─ s3.py            # S3 implementation
│  │   ├─ parser/
│  │   │   └─ tfstate.py       # Terraform state parser
│  │   ├─ es.py                # Elasticsearch client + bulk operations
│  │   └─ main.py              # FastAPI entrypoint
│  ├─ tests/
│  │   ├─ unit/                # Unit tests
│  │   └─ integration/         # Integration tests
│  ├─ Dockerfile
│  └─ pyproject.toml           # Python dependencies
├─ examples/
│  ├─ sample-terraform.tfstate # Sample data
│  └─ setup-demo.sh           # Demo setup script
├─ docker-compose.yml
└─ README.md
```

### Running Tests

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
```

### Local Development

```bash
# Start just the infrastructure
docker compose up opensearch opensearch-dashboards localstack

# Run the backend locally
cd backend
pip install -e .[dev]
export S3_ENDPOINT_URL=http://localhost:4566
export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test
uvicorn indexer.main:app --reload
```

## API Endpoints

- `GET /` - Health check
- `GET /stats` - Indexing statistics
- `POST /search` - Search terraform resources (Elasticsearch query DSL)

Example search:
```bash
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

### Custom Transformers

The parsing pipeline can be extended by modifying `TfStateParser` or implementing additional processing steps.

## Monitoring

- View indexing progress in container logs: `docker compose logs -f terraform-indexer`
- Check Elasticsearch health: http://localhost:9200/_cluster/health
- Monitor indexing stats: http://localhost:8000/stats

## Troubleshooting

**No documents appearing in OpenSearch:**
- Check that tfstate files are being uploaded to the correct S3 bucket/prefix
- Verify container logs for parsing errors
- Ensure Elasticsearch is healthy

**Connection errors:**
- Verify all services are running: `docker compose ps`
- Check service logs: `docker compose logs [service-name]`
- Ensure ports are not conflicting with other services

**Performance issues:**
- Adjust `ES_BATCH_SIZE` and `ES_BATCH_TIMEOUT` for your workload
- Increase `S3_POLL_INTERVAL` if processing large state files
- Scale Elasticsearch resources if needed