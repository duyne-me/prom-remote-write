# Quick Start Guide

Get the Multi-Environment Multi-Cluster monitoring stack running in 10 minutes.

## Prerequisites

- Docker Desktop (or Docker Engine + Docker Compose)
- 8GB+ available RAM
- Ports 3001, 9091, 9115, 2112, 8429-8434 available

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
- **Mock Exporter** (Python) - Generates 340+ production-like metrics
- **VictoriaMetrics Cluster** - 2x vminsert, 2x vmselect, 2x vmstorage
- **5 vmagent Instances**:
  - ap-southeast-1-dev-eks-01 (dev environment)
  - us-east-1-prod-eks-01 (prod HA cluster 1)
  - us-east-1-prod-eks-02 (prod HA cluster 2)
  - eu-west-1-prod-eks-01 (prod)
  - ap-southeast-1-prod-eks-01 (prod)
- **vmagent-receiver-scraper** - For legacy push flow
- **prometheus-receiver** - Remote write endpoint
- **blackbox-exporter** - Network probes
- **Grafana** - 4 pre-configured dashboards

## Step 3: Verify Services

Check that all services are running:

```bash
docker compose ps
```

Expected output: 16 containers all in "Up" state.

### Verify Specific Components

```bash
# Check vmagents are scraping
curl -s http://localhost:8429/metrics | grep scrape_duration_seconds

# Check vmagents are remote writing
curl -s http://localhost:8430/metrics | grep vmagent_remotewrite_samples_total

# Check mock exporter
curl -s http://localhost:2112/metrics | head -20

# Check prometheus-receiver
curl -s http://localhost:9091/metrics | grep prometheus_remote_storage
```

## Step 4: Access Grafana

Open Grafana in your browser:

```
http://localhost:3001
```

Login (anonymous access enabled, no credentials required).

## Step 5: Explore Dashboards

Grafana includes 4 production-ready dashboards:

### 1. Global Infrastructure Overview
**URL**: `/d/global-infrastructure`

**Quick Check**:
- Total Ingestion Rate should be > 0
- All 5 vmagents should show as active
- Cluster Status table: all clusters should be green (UP)

### 2. Application Performance (RED)
**URL**: `/d/application-performance`

**Quick Check**:
- Select Environment: prod
- Select Cluster: us-east-1-prod-eks-01
- Request Rate should show traffic
- Error Rate should be low (< 5%)
- Latency heatmap shows distribution

### 3. Monitoring Stack Health
**URL**: `/d/monitoring-stack-health`

**Quick Check**:
- Remote Write Latency (p95) should be < 1s
- Pending Bytes should be near 0
- All VictoriaMetrics components should be UP (green)

### 4. Cross-Region Latency Monitoring
**URL**: `/d/cross-region-latency`

**Quick Check**:
- Probe Success Rate should be 100%
- Probe duration shows network latency
- No failing probes in table

## Step 6: Run Test Queries

### Query VictoriaMetrics Directly

```bash
# Check total metrics
curl -s 'http://localhost:8481/select/0/prometheus/api/v1/query?query=count(up)' | jq

# Query by environment
curl -s 'http://localhost:8481/select/0/prometheus/api/v1/query?query=up{env="prod"}' | jq

# Query by cluster
curl -s 'http://localhost:8481/select/0/prometheus/api/v1/query?query=up{cluster="us-east-1-prod-eks-01"}' | jq
```

### Use Grafana Explore

1. Go to Explore (compass icon in left sidebar)
2. Select datasource: VictoriaMetrics
3. Try queries:
```promql
# All metrics from prod environment
{env="prod"}

# Request rate by cluster
sum(rate(http_requests_total[5m])) by (cluster)

# vmagent remote write latency P95
histogram_quantile(0.95, sum(rate(vmagent_remotewrite_send_duration_seconds_bucket[5m])) by (le, cluster))

# Scrape duration by cluster
histogram_quantile(0.95, sum(rate(scrape_duration_seconds_bucket[5m])) by (le, cluster))
```

## Step 7: Test Legacy Push Flow

Simulate external system remote writing to prometheus-receiver:

```bash
# Generate test metrics
cat > /tmp/test-metrics.txt << 'EOF'
# HELP test_metric A test metric
# TYPE test_metric gauge
test_metric{env="external",service="test"} 42
EOF

# Remote write to prometheus-receiver
curl -X POST http://localhost:9091/api/v1/write \
  --data-binary @/tmp/test-metrics.txt \
  -H "Content-Type: application/x-protobuf" \
  -H "Content-Encoding: snappy"
```

Note: For real remote write, use Prometheus native remote write protocol.

## Step 8: Simulate Network Latency (Optional)

Test how system behaves under different latency conditions:

```bash
# Add 100ms latency to EU cluster
./scripts/simulate-latency.sh add vmagent-eu-west-1-prod-eks-01 100 20

# Watch "Monitoring Stack Health" dashboard
# Remote Write Latency should increase for EU cluster

# Remove latency
./scripts/simulate-latency.sh remove vmagent-eu-west-1-prod-eks-01
```

See [Network Latency Simulation Guide](network-latency-simulation.md) for detailed testing scenarios.

## Verification Checklist

After completing quick start, verify:

- [ ] All 16 containers running (`docker compose ps`)
- [ ] Grafana accessible at localhost:3001
- [ ] Global Infrastructure dashboard shows 5 active vmagents
- [ ] Application Performance dashboard has data for dev and prod
- [ ] Monitoring Stack Health shows remote write latency < 2s
- [ ] Cross-Region Latency dashboard shows probe data
- [ ] VictoriaMetrics query returns data
- [ ] Mock exporter accessible at localhost:2112

## Common Issues

### Port Already in Use

Check which process is using the port:

```bash
# On Linux/Mac
lsof -i :3001

# On Windows
netstat -ano | findstr :3001
```

**Solution**: Change port mapping in `docker-compose.yml` or stop conflicting service.

### vmagent Not Sending Metrics

**Symptoms**: Dashboard shows "No Data"

**Check**:
```bash
# Check vmagent logs
docker logs vmagent-us-east-1-prod-eks-01

# Check if vmagent can reach vminsert
docker exec vmagent-us-east-1-prod-eks-01 wget -O- http://vminsert-1:8480/health

# Check vmagent metrics
curl http://localhost:8430/metrics | grep remotewrite
```

### Services Won't Start

Check logs for specific service:

```bash
# All services
docker compose logs

# Specific service
docker compose logs vmagent-us-east-1-prod-eks-01
docker compose logs vminsert-1
docker compose logs vmstorage-1
```

### Grafana Shows "No Data"

1. **Wait 1-2 minutes**: Metrics need time to flow through pipeline
2. **Check datasource**: Grafana → Configuration → Data Sources → VictoriaMetrics → Test
3. **Check query in Explore**: Test query directly before using dashboard
4. **Verify labels**: Make sure query labels match actual metric labels

### Dashboard Variables Empty

**Symptoms**: $env or $cluster dropdown is empty

**Causes**:
- Services just started (wait 1-2 min)
- No metrics with that label yet
- Datasource not configured correctly

**Solution**:
```bash
# Verify metrics exist with label
curl -s 'http://localhost:8481/select/0/prometheus/api/v1/label/env/values' | jq
curl -s 'http://localhost:8481/select/0/prometheus/api/v1/label/cluster/values' | jq
```

## Next Steps

1. **Explore Dashboards**: Familiarize yourself with all 4 dashboards
2. **Read Architecture Guide**: Understand the 3 data flows
3. **Review Latency Monitoring**: Learn about critical latency metrics
4. **Test Latency Simulation**: Understand system behavior under load
5. **Customize**: Add your own applications, create custom dashboards

## Additional Resources

- [Architecture Overview](../architecture/overview.md) - Detailed architecture
- [Dashboard Guide](dashboard-guide.md) - How to use each dashboard
- [Latency Monitoring](latency-monitoring.md) - Comprehensive latency guide
- [Metrics Reference](../metrics/reference.md) - All available metrics
- [Network Latency Simulation](network-latency-simulation.md) - Testing guide

## Getting Help

If you encounter issues:
1. Check logs: `docker compose logs [service]`
2. Verify network: `docker network inspect prom-remote-writer_promnet`
3. Check troubleshooting guide (coming soon)
4. Open GitHub issue with logs and config

## Cleanup

To completely remove the stack:

```bash
# Stop and remove containers
docker compose down

# Remove all data (volumes)
docker compose down -v

# Remove downloaded images (optional)
docker compose down --rmi all -v
```
