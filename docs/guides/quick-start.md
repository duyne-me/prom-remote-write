# Quick Start Guide

Get the Prometheus Remote Write Demo running in 10 minutes.

## Prerequisites

- Docker Desktop (or Docker Engine + Docker Compose)
- 8GB+ available RAM
- Ports 3001, 9091, 9092, 8427, 2112, 8480-8482 available

## Step 1: Clone Repository

```bash
git clone <repository-url>
cd prom-remote-writer
```

## Step 2: Start Services

Start all services with Docker Compose:

```bash
docker compose up -d
```

This will start:
- Mock Exporter (Python) - Generates metrics
- VictoriaMetrics Cluster (6 nodes)
- 4 vmagent instances (multi-region simulation)
- Prometheus Writer and Receiver
- Grafana with pre-configured dashboards

## Step 3: Verify Services

Check that all services are running:

```bash
docker compose ps
```

Expected output shows all containers in "Up" state.

## Step 4: Access Grafana

Open Grafana in your browser:

```
http://localhost:3001
```

Default credentials:
- Username: `admin`
- Password: `admin`

## Step 5: Explore Dashboards

Grafana includes 5 pre-configured dashboards:

1. **Infrastructure** - Node and system metrics (USE method)
2. **Application** - Application business metrics
3. **Multi-Region Overview** - Compare metrics across regions
4. **Cross-Region Latency** - Latency between regions
5. **SLO/SLI** - Service level objectives and indicators

## Step 6: Explore Metrics

Access the mock exporter directly:

```bash
curl http://localhost:2112/metrics | head -50
```

Access VictoriaMetrics:

```bash
curl http://localhost:8427/api/v1/query?query=up
```

## Stopping Services

To stop all services:

```bash
docker compose down
```

To stop and remove all data:

```bash
docker compose down -v
```

## Next Steps

- Read the [Architecture Overview](../architecture/overview.md)
- Explore the [Metrics Reference](../metrics/reference.md)
- Review [Configuration Guide](configuration.md)

## Common Issues

### Port Already in Use

If a port is already in use, edit `docker-compose.yml` to change port mappings.

### Services Won't Start

Check logs for errors:

```bash
docker compose logs [service-name]
```

### Grafana Not Loading

Wait 30-60 seconds for all services to initialize, then refresh the browser.

For more troubleshooting, see the [Troubleshooting Guide](troubleshooting.md).

