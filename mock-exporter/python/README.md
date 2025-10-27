# Mock Metrics Exporter (Python)

Production-like metrics exporter for Prometheus remote write demo, implemented in Python with uv package management.

## Features

- **20+ Production Metrics**: HTTP service (RED), Node system (USE), and Application business metrics
- **Prometheus Naming Conventions**: Follows official naming standards
- **Realistic Data Simulation**: Generates realistic metric values with variation
- **Async Architecture**: FastAPI + asyncio for high performance
- **Configurable**: YAML-based configuration for easy customization

## Quick Start

### Using uv (recommended)

```bash
# Install dependencies
uv sync

# Run locally
uv run main.py

# Or with custom config
CONFIG_PATH=my-config.yml uv run main.py
```

### Using Docker

```bash
# Build image
docker build -t mock-exporter-python .

# Run container
docker run -p 2112:2112 mock-exporter-python
```

## Configuration

Edit `config.yml` to customize metrics:

- `label_metrics`: Info-style metrics with static labels
- `http_metrics`: HTTP service metrics (RED method)
- `node_metrics`: System/node metrics (USE method)  
- `app_metrics`: Application business metrics

## Metrics Generated

### HTTP Service Metrics (RED)
- `http_request_duration_seconds` (histogram)
- `http_requests_total` (counter)
- `http_request_size_bytes` (histogram)
- `http_response_size_bytes` (histogram)

### Node/System Metrics (USE)
- `node_cpu_seconds_total` (counter)
- `node_memory_MemTotal_bytes` (gauge)
- `node_memory_MemAvailable_bytes` (gauge)
- `node_disk_io_time_seconds_total` (counter)
- `node_network_transmit_bytes_total` (counter)
- `node_network_receive_bytes_total` (counter)
- `node_filesystem_size_bytes` (gauge)
- `node_filesystem_avail_bytes` (gauge)

### Application Metrics
- `app_errors_total` (counter)
- `app_database_queries_duration_seconds` (histogram)
- `app_database_connections_active` (gauge)
- `app_cache_requests_total` (counter)
- `app_queue_size` (gauge)
- `app_worker_tasks_duration_seconds` (histogram)
- `app_business_transactions_total` (counter)

## Endpoints

- `GET /metrics` - Prometheus metrics endpoint
- `GET /healthz` - Health check
- `GET /` - Service information

## Environment Variables

- `HOST` - Server host (default: 0.0.0.0)
- `PORT` - Server port (default: 2112)
- `LOG_LEVEL` - Logging level (default: info)
- `CONFIG_PATH` - Path to config file (default: config.yml)

## Development

```bash
# Install dev dependencies
uv sync --dev

# Format code
uv run black main.py

# Sort imports
uv run isort main.py

# Run tests
uv run pytest
```
