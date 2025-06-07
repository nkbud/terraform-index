# terraform-indexer

A queue-based pipeline that collects Terraform `.tfstate` files from multiple sources (local filesystem, S3, and Kubernetes), parses them, and indexes them into Elasticsearch for powerful exploration and search.

**Get a running demo in 30 seconds:**
```bash
git clone https://github.com/nkbud/terraform-index.git
cd terraform-index
make setup
```
🎉 **Done!** Visit http://localhost:3000 to explore your infrastructure.

## What This Does

Transform your scattered Terraform state files into a searchable, explorable infrastructure database:

```
📁 .tfstate files + ☁️ S3 buckets + ⚓ K8s secrets  →  🔍 Powerful Search UI
```

**Before:** Terraform state scattered across files, S3 buckets, and Kubernetes secrets  
**After:** Unified search and exploration of all your infrastructure resources

## Quick Start

### Option 1: Instant Demo (Recommended)
```bash
# Complete setup with sample data
make setup

# View your infrastructure
open http://localhost:3000
```

### Option 2: Step-by-Step
```bash
# 1. Start the system
docker compose up --build -d

# 2. Add your .tfstate files
cp your-terraform.tfstate ./tfstates/

# 3. Explore at http://localhost:3000
```

## What You Get

### 🔍 **Advanced Search Interface**
- **Full-text search** across all resource attributes
- **Multi-field filtering** (type=aws_instance AND region=us-east-1)
- **Fuzzy matching** for typos and partial matches
- **Drill-down exploration** - click to find similar resources

### 📊 **Infrastructure Discovery**
- **Resource relationships** - see how components connect
- **Source tracking** - know exactly where each resource comes from
- **Time-based insights** - understand when resources were last updated
- **Cross-environment visibility** - search across dev, staging, and prod

### 🎯 **Real Use Cases**
```bash
# Find all production RDS instances
Search: "RDS production"

# Multi-key search for security audit
Key: "type" Value: "aws_security_group"
Key: "environment" Value: "production"

# Find resources by tag
Search: "tag:Environment=staging"

# Discover resource relationships
Click "Similar Type" → See all resources of same type
Click "Same Region" → See all resources in that region
```

## Data Sources

### 📁 **Local Filesystem**
Automatically watches `./tfstates/` directory for `.tfstate` files

### ☁️ **AWS S3**
- Supports multiple buckets
- Works with real AWS S3 or Localstack (for local dev)
- Searches entire buckets for `*.tfstate` files

### ⚓ **Kubernetes Clusters**
- Finds Terraform state stored as Kubernetes secrets
- Supports multiple clusters and namespaces
- Compatible with Terraform's Kubernetes backend

## Configuration

The system has two modes for different environments:

### 🏠 **Local Development** (`.env.local`)
- Processes files from `./tfstates/` directory
- Uses Localstack for S3 simulation
- Debug logging enabled
- Perfect for testing and development

### ☁️ **Production** (`.env.prod`)
- Connects to real AWS S3 buckets
- Monitors production Kubernetes clusters
- Structured JSON logging
- Production-ready configuration

Switch between modes:
```bash
# Local development
cp .env.local .env
make demo-local

# Production  
cp .env.prod .env
make demo-prod
```

## Connecting Your Real Data

### Step 1: Configure S3 Access
Edit `.env.prod`:
```bash
# Your S3 buckets (JSON array)
S3_BUCKETS=["your-terraform-states", "your-backup-bucket"]

# AWS credentials
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
```

### Step 2: Configure Kubernetes Access
Edit `.env.prod`:
```bash
# Enable Kubernetes collection
KUBERNETES_ENABLED=true

# Your clusters (JSON array)
KUBERNETES_CLUSTERS=[
  {
    "name": "production",
    "kubeconfig": "/path/to/prod-kubeconfig",
    "context": "prod-context",
    "namespaces": ["terraform", "infrastructure"]
  },
  {
    "name": "staging",
    "kubeconfig": "/path/to/staging-kubeconfig",
    "context": "staging-context", 
    "namespaces": ["default", "terraform"]
  }
]
```

### Step 3: Start with Your Data
```bash
# Copy production config
cp .env.prod .env

# Start the system
make demo-prod

# Monitor progress
make logs
```

## Commands Reference

| Command | Purpose |
|---------|---------|
| `make setup` | **Complete setup + demo (recommended first run)** |
| `make demo-local` | Local development demo |
| `make demo-prod` | Production demo with real data |
| `make logs` | View live logs |
| `make status` | Pipeline status and stats |
| `make ui` | Open search interface |
| `make clean` | Reset everything |

## How It Works

The system uses a queue-based architecture with three independent stages:

```
┌─────────────────┐     Queue 1     ┌──────────────┐     Queue 2     ┌────────────────┐
│   COLLECTORS    │ ─────────────────► │    PARSER    │ ─────────────────► │   UPLOADER     │
│ • Filesystem    │  (raw tfstate)  │ • TfState    │  (parsed docs)  │ • Elasticsearch│
│ • S3 (AWS/Local)│                 │   Parser     │                 │   Bulk API     │
│ • Kubernetes    │                 │              │                 │                │
└─────────────────┘                 └──────────────┘                 └────────────────┘
                                                                              │
                                                                       ┌──────▼─────────┐
                                                                       │ Search UI      │
                                                                       │ localhost:3000 │
                                                                       └────────────────┘
```

**Benefits:**
- **Decoupled processing** - each stage runs independently
- **Fault tolerant** - workers continue on individual file errors  
- **Scalable** - easy to add more workers or sources
- **Real-time** - new files are processed automatically

## Sample Data

The system includes sample Terraform state files for immediate testing:

- **Web Application** - EC2 instances, security groups, load balancers
- **Database Cluster** - RDS cluster with multiple instances
- **Network Infrastructure** - VPCs, subnets, route tables

These files are automatically processed when you run `make setup`.

## API Endpoints

- **Search UI**: http://localhost:3000
- **API Health**: http://localhost:8000  
- **Pipeline Stats**: http://localhost:8000/stats
- **Search API**: http://localhost:8000/search
- **API Docs**: http://localhost:8000/docs

Example API usage:
```bash
# Get pipeline statistics
curl http://localhost:8000/stats | jq

# Search for AWS instances
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

## Troubleshooting

### No documents appearing?
```bash
# Check pipeline status
make status

# View logs
make logs

# Verify sample data exists
ls ./tfstates/
```

### Connection errors?
```bash
# Check all services are running
docker compose ps

# Health check
make health

# Full troubleshooting
make troubleshoot
```

### Performance issues?
```bash
# Monitor queue sizes
make stats

# View detailed logs
LOG_LEVEL=DEBUG make demo-local
```

## Development

### Setup Development Environment
```bash
# Install dependencies
make dev-setup

# Run tests
make test

# Format code
make format

# Run individual components
docker compose exec terraform-indexer python scripts/run_component.py filesystem
```

### Architecture

```
terraform-indexer/
├─ backend/src/indexer/
│   ├─ collector/          # Data source collectors
│   ├─ parser/             # Terraform state parser  
│   ├─ queue/              # Queue implementations
│   ├─ pipeline.py         # Worker components
│   └─ main.py             # FastAPI application
├─ ui/                     # React search interface
├─ scripts/                # Demo and testing scripts
├─ tfstates/               # Sample data
├─ Makefile                # Quick commands
└─ docker-compose.yml      # Full stack setup
```

## Extensibility

### Adding New Data Sources
```python
from indexer.collector.base import BaseCollector

class GitCollector(BaseCollector):
    async def collect(self):
        # Implement Git repository scanning
        yield {"content": tfstate_dict, "metadata": source_info}
```

### Custom Search Features
The search UI is built with React and can be easily extended with new features, filters, and visualizations.

---

**Questions?** Check the [API docs](http://localhost:8000/docs) or run `make troubleshoot` for diagnostic information.

## Kubernetes Collector

The system supports collecting Terraform state files stored as Kubernetes secrets, commonly used with Terraform's Kubernetes backend.

### 🔧 **Configuration**

Add Kubernetes support to your `.env` file:

```bash
# Enable Kubernetes collector
KUBERNETES_ENABLED=true
KUBERNETES_POLL_INTERVAL=60
KUBERNETES_SECRET_LABEL_SELECTOR=app.terraform.io/component=backend-state
KUBERNETES_SECRET_NAME_PATTERN=tfstate-

# Define clusters to search (JSON format)
KUBERNETES_CLUSTERS='[
  {
    "name": "production",
    "kubeconfig": "/path/to/prod-kubeconfig",
    "context": "prod-context", 
    "namespaces": ["terraform", "infrastructure"]
  },
  {
    "name": "staging",
    "kubeconfig": "/path/to/staging-kubeconfig",
    "context": "staging-context",
    "namespaces": ["default", "terraform"]
  }
]'
```

### 🎯 **Features**
- **Multi-cluster support** - search across multiple Kubernetes clusters
- **Namespace filtering** - specify which namespaces to search in each cluster
- **Flexible discovery** - finds secrets by labels or name patterns
- **Multiple context support** - use different kubectl contexts per cluster
- **Robust error handling** - continues processing if individual clusters are unavailable

### 📝 **Secret Format Support**

The collector looks for Terraform state in these secret keys:
- `tfstate` (primary)
- `state` (alternative)
- `terraform.tfstate` (common format)
- `default.tfstate` (terraform default)

Example Kubernetes secret:
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: tfstate-production
  labels:
    app.terraform.io/component: backend-state
  annotations:
    terraform.workspace: production
type: Opaque
data:
  tfstate: <base64-encoded-terraform-state>
```

### 🚀 **Demo & Testing**

```bash
# Test the Kubernetes collector
python scripts/demo_kubernetes.py

# Create a test secret for local testing
kubectl create secret generic tfstate-demo \
  --from-file=tfstate=/path/to/your/terraform.tfstate \
  --annotation='app.terraform.io/component=backend-state'
```

### ⚙️ **Cluster Configuration Options**

Each cluster configuration supports:
- `name`: Unique cluster identifier
- `kubeconfig`: Path to kubeconfig file (optional - uses default if omitted)
- `context`: kubectl context name (optional - uses current context if omitted)  
- `namespaces`: List of namespaces to search (optional - searches all if omitted)

For in-cluster deployments, omit `kubeconfig` and `context` to use pod service account.

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
| `S3_BUCKETS` | `terraform-states` | S3 buckets to poll (comma-separated) |
| `S3_POLL_INTERVAL` | `30` | Poll interval in seconds |
| `S3_ENDPOINT_URL` | `None` | Custom S3 endpoint (for LocalStack) |
| `AWS_ACCESS_KEY_ID` | `None` | AWS credentials |
| `AWS_SECRET_ACCESS_KEY` | `None` | AWS credentials |
| **Filesystem Configuration** | | |
| `FILESYSTEM_WATCH_DIRECTORY` | `./tfstates` | Local directory to watch |
| `FILESYSTEM_POLL_INTERVAL` | `5` | Filesystem poll interval in seconds |
| `FILESYSTEM_ENABLED` | `true` | Enable filesystem watching |
| **Kubernetes Configuration** | | |
| `KUBERNETES_ENABLED` | `false` | Enable Kubernetes secret collection |
| `KUBERNETES_POLL_INTERVAL` | `60` | Poll interval in seconds |
| `KUBERNETES_SECRET_LABEL_SELECTOR` | `app.terraform.io/component=backend-state` | Label selector for secrets |
| `KUBERNETES_SECRET_NAME_PATTERN` | `tfstate-` | Name pattern for secrets |
| `KUBERNETES_CLUSTERS` | `""` | JSON string of cluster configurations |
| **Elasticsearch Configuration** | | |
| `ES_HOSTS` | `http://localhost:9200` | Elasticsearch hosts |
| `ES_INDEX` | `terraform-resources` | Index name |
| `ES_BATCH_SIZE` | `100` | Bulk indexing batch size |
| `ES_BATCH_TIMEOUT` | `10` | Bulk indexing timeout (seconds) |

## Features

### Pipeline Architecture
- ✅ **Queue-based processing**: Independent collector, parser, and uploader stages
- ✅ **Multiple sources**: Filesystem, S3 (AWS or Localstack), and Kubernetes clusters
- ✅ **Local development**: Full local setup with sample files
- ✅ **Configuration-driven**: Switch between local/cloud modes
- ✅ **Custom Search UI**: Advanced exploration interface with drill-down capabilities

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
| `scripts/demo_kubernetes.py` | Test Kubernetes collector with multiple clusters |
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