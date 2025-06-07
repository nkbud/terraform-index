FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies directly
RUN pip install --no-cache-dir \
    boto3>=1.34.0 \
    elasticsearch>=8.0.0 \
    fastapi>=0.100.0 \
    uvicorn[standard]>=0.20.0 \
    pydantic>=2.0.0 \
    pydantic-settings>=2.0.0 \
    httpx>=0.24.0 \
    kubernetes>=28.0.0

# Copy source code
COPY src/ ./src/

# Expose port
EXPOSE 8000

# Set Python path
ENV PYTHONPATH=/app/src

# Run the application
CMD ["uvicorn", "indexer.main:app", "--host", "0.0.0.0", "--port", "8000"]