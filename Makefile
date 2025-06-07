# Terraform Indexer Makefile
# Quick setup, demo, and management commands

.PHONY: help setup demo demo-local demo-prod test clean logs status ui

# Default target
help:
	@echo "🚀 Terraform Indexer - Quick Commands"
	@echo ""
	@echo "Setup & Demo:"
	@echo "  make setup      - Complete setup and start demo (recommended first run)"
	@echo "  make demo       - Start full demo with sample data"
	@echo "  make demo-local - Start local demo (filesystem + localstack)"
	@echo "  make demo-prod  - Start production demo (real AWS S3 + K8s)"
	@echo ""
	@echo "Development:"
	@echo "  make dev-setup  - Setup development environment"
	@echo "  make test       - Run all tests"
	@echo "  make lint       - Run code linting"
	@echo "  make format     - Format code"
	@echo ""
	@echo "Operations:"
	@echo "  make start      - Start services"
	@echo "  make stop       - Stop services"
	@echo "  make restart    - Restart services"
	@echo "  make logs       - Show logs"
	@echo "  make status     - Show status"
	@echo "  make clean      - Clean up containers and data"
	@echo ""
	@echo "UI & Tools:"
	@echo "  make ui         - Open search UI (localhost:3000)"
	@echo "  make api        - Open API docs (localhost:8000/docs)"
	@echo "  make stats      - Show pipeline stats"

# Complete setup and demo - recommended for first-time users
setup:
	@echo "🎯 Setting up Terraform Indexer..."
	@echo "📦 Building containers..."
	docker compose build
	@echo "🚀 Starting services..."
	docker compose up -d
	@echo "⏳ Waiting for services to be ready..."
	@sleep 15
	@echo "📁 Seeding sample data..."
	@make seed-data
	@echo ""
	@echo "🎉 Setup complete! Your infrastructure search is ready:"
	@echo ""
	@echo "  🔍 Search UI:  http://localhost:3000"
	@echo "  📊 API:        http://localhost:8000"  
	@echo "  📖 API Docs:   http://localhost:8000/docs"
	@echo "  📈 Stats:      http://localhost:8000/stats"
	@echo ""
	@echo "  📋 Logs:       make logs"
	@echo "  📊 Status:     make status"
	@echo ""

# Local development demo
demo-local:
	@echo "🏠 Starting local development demo..."
	@cp .env.local .env
	docker compose down -v
	docker compose up --build -d
	@sleep 10
	@make seed-data
	@echo "✅ Local demo ready at http://localhost:3000"

# Production demo (requires real AWS credentials)
demo-prod:
	@echo "☁️ Starting production demo..."
	@if [ ! -f .env.prod ]; then echo "❌ .env.prod not found. Copy and configure .env.prod first."; exit 1; fi
	@cp .env.prod .env
	docker compose down -v
	docker compose up --build -d
	@echo "✅ Production demo ready at http://localhost:3000"

# Quick demo with current settings
demo:
	@echo "🚀 Starting demo with current configuration..."
	docker compose up --build -d
	@sleep 10
	@make seed-data
	@echo "✅ Demo ready at http://localhost:3000"

# Development environment setup
dev-setup:
	@echo "🛠️ Setting up development environment..."
	@if [ ! -d "backend/venv" ]; then \
		echo "📦 Creating Python virtual environment..."; \
		cd backend && python -m venv venv; \
	fi
	@echo "📦 Installing Python dependencies..."
	@cd backend && source venv/bin/activate && pip install -e .[dev]
	@if [ ! -d "ui/node_modules" ]; then \
		echo "📦 Installing Node.js dependencies..."; \
		cd ui && npm install; \
	fi
	@echo "✅ Development environment ready"

# Start services
start:
	@echo "🚀 Starting terraform indexer..."
	docker compose up -d

# Stop services  
stop:
	@echo "🛑 Stopping terraform indexer..."
	docker compose down

# Restart services
restart:
	@echo "🔄 Restarting terraform indexer..."
	docker compose down
	docker compose up -d

# Show logs
logs:
	@echo "📋 Recent logs (Ctrl+C to exit, 'f' to follow):"
	docker compose logs --tail=50 -f

# Show pipeline status
status:
	@echo "📊 Terraform Indexer Status:"
	@echo ""
	@echo "🐳 Docker Services:"
	@docker compose ps
	@echo ""
	@echo "📈 Pipeline Stats:"
	@curl -s http://localhost:8000/stats 2>/dev/null | python -m json.tool 2>/dev/null || echo "❌ API not available"

# Show just pipeline stats
stats:
	@curl -s http://localhost:8000/stats | python -m json.tool

# Seed sample data
seed-data:
	@echo "📁 Seeding sample data..."
	@sleep 5  # Wait for localstack to be ready
	@docker compose exec terraform-indexer python scripts/seed_s3.py || echo "⚠️ S3 seeding failed (services may still be starting)"
	@echo "✅ Sample .tfstate files available in ./tfstates/ and localstack S3"

# Run tests
test:
	@echo "🧪 Running tests..."
	@cd backend && source venv/bin/activate && pytest tests/ -v

# Run integration tests
test-integration:
	@echo "🔗 Running integration tests..."
	docker compose up -d opensearch localstack
	@sleep 10
	@cd backend && source venv/bin/activate && pytest tests/integration/ -v

# Run linting
lint:
	@echo "🔍 Running linting..."
	@cd backend && source venv/bin/activate && \
		black --check src/ tests/ && \
		isort --check src/ tests/ && \
		mypy src/

# Format code
format:
	@echo "✨ Formatting code..."
	@cd backend && source venv/bin/activate && \
		black src/ tests/ && \
		isort src/ tests/

# Clean up everything
clean:
	@echo "🧹 Cleaning up..."
	docker compose down -v --remove-orphans
	docker system prune -f
	@echo "✅ Cleanup complete"

# Clean up data only
clean-data:
	@echo "🗑️ Cleaning up data volumes..."
	docker compose down -v
	@echo "✅ Data cleanup complete"

# Open search UI
ui:
	@echo "🔍 Opening search UI..."
	@python -c "import webbrowser; webbrowser.open('http://localhost:3000')" 2>/dev/null || \
		echo "🔍 Search UI: http://localhost:3000"

# Open API docs
api:
	@echo "📖 Opening API documentation..."
	@python -c "import webbrowser; webbrowser.open('http://localhost:8000/docs')" 2>/dev/null || \
		echo "📖 API Docs: http://localhost:8000/docs"

# Component testing
test-components:
	@echo "🔧 Testing individual components..."
	@docker compose exec terraform-indexer python scripts/test_components.py

# Demo scripts
demo-filesystem:
	@echo "📁 Running filesystem demo..."
	@docker compose exec terraform-indexer python scripts/simple_demo.py

demo-s3:
	@echo "☁️ Running S3 demo..."
	@docker compose exec terraform-indexer python scripts/run_component.py s3

demo-k8s:
	@echo "⚓ Running Kubernetes demo..."
	@docker compose exec terraform-indexer python scripts/demo_kubernetes.py

# Show configuration
config:
	@echo "⚙️ Current configuration:"
	@if [ -f .env ]; then \
		echo "Using .env:"; \
		grep -E "^[A-Z]" .env | head -10; \
	else \
		echo "No .env file found"; \
	fi

# Health check
health:
	@echo "🏥 Health check:"
	@curl -s http://localhost:8000/ | python -m json.tool 2>/dev/null || echo "❌ API not responding"

# Quick troubleshooting
troubleshoot:
	@echo "🔧 Troubleshooting Terraform Indexer:"
	@echo ""
	@echo "📊 Service Status:"
	@docker compose ps
	@echo ""
	@echo "📋 Recent Errors:"
	@docker compose logs --tail=20 terraform-indexer | grep -i error || echo "No recent errors found"
	@echo ""
	@echo "🔗 Connectivity:"
	@curl -s http://localhost:8000/ >/dev/null && echo "✅ API responding" || echo "❌ API not responding"
	@curl -s http://localhost:3000/ >/dev/null && echo "✅ UI responding" || echo "❌ UI not responding"
	@curl -s http://localhost:9200/ >/dev/null && echo "✅ Elasticsearch responding" || echo "❌ Elasticsearch not responding"