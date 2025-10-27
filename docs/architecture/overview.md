# Architecture Overview

## System Architecture

This project demonstrates two observability architectures side-by-side:

1. **Prometheus Native**: Prometheus Writer → Prometheus Receiver
2. **VictoriaMetrics Production**: vmagent (multi-region) → vminsert → vmstorage ← vmselect

## Data Flow

### Flow 1: Prometheus Native

```
mock-exporter-python:2112/metrics
    ↓ (scrape)
prometheus-writer:9090
    ↓ (remote_write)
prometheus-receiver:9091
    ↓ (query)
Grafana:3001
```

**Configuration**: `prometheus/writer.yml`
- Scrape interval: 5s
- Remote write timeout: 30s
- Labels: `cluster=staging-cluster`, `region=local`, `environment=staging`

**Purpose**: Demonstrates standard Prometheus-to-Prometheus remote write pattern for comparison.

### Flow 2: VictoriaMetrics Multi-Region

```
mock-exporter-python:2112/metrics
    ↓ (scrape × 4)
vmagent-us-east-1    vmagent-eu-west-1    vmagent-ap-southeast-1    vmagent-sa-east-1
    ↓ (external_labels)  ↓ (external_labels)  ↓ (external_labels)    ↓ (external_labels)
    region=us-east-1     region=eu-west-1     region=ap-southeast-1   region=sa-east-1
    cluster=prod-us      cluster=prod-eu      cluster=prod-apac      cluster=prod-sa
    environment=prod     environment=prod     environment=prod       environment=prod
    ↓ (remote_write)     ↓ (remote_write)     ↓ (remote_write)       ↓ (remote_write)
                vminsert-1:8480    vminsert-2:8480
                        ↓ (distribute)
                vmstorage-1:8482   vmstorage-2:8482
                        ↓ (query)
                vmselect-1:8481    vmselect-2:8481
                        ↓ (query)
                    Grafana:3001
```

**Purpose**: Simulates production multi-region deployment where each region adds distinct labels to the same metrics.

## VictoriaMetrics Cluster Components

### vmstorage (Storage Layer)

**Function**: Persistent storage for time series data.

| Property | Value |
|----------|-------|
| Replicas | 2 (vmstorage-1, vmstorage-2) |
| Port | 8482 |
| Data Path | `/vmstorage-data` |
| Retention | 1 year |
| Replication | Yes (data replicated between nodes) |

**Responsibilities**:
- Store compressed time series data
- Replicate data for high availability
- Handle data retention policies
- Optimize storage compression

### vminsert (Ingestion Layer)

**Function**: Receive remote write requests and distribute data to storage nodes.

| Property | Value |
|----------|-------|
| Replicas | 2 (vminsert-1, vminsert-2) |
| Port | 8480 |
| Load Balancing | Direct connection from vmagents |

**Responsibilities**:
- Accept metrics via remote write protocol
- Distribute data across storage nodes
- Handle ingestion rate limits
- Provide ingestion health metrics

### vmselect (Query Layer)

**Function**: Query time series data from storage nodes and serve queries.

| Property | Value |
|----------|-------|
| Replicas | 2 (vmselect-1, vmselect-2) |
| Port | 8481 |
| Query API | Prometheus-compatible |

**Responsibilities**:
- Execute PromQL queries
- Aggregate results from storage nodes
- Cache query results
- Handle concurrent query requests

## vmagent Labeling Strategy

### External Labels

External labels are applied to ALL scraped metrics by vmagent:

```yaml
global:
  external_labels:
    region: "us-east-1"
    cluster: "prod-us-k8s"
    environment: "production"
    datacenter: "us-east-1a"
```

**Why external_labels?**
- Applied automatically to all metrics
- Single source of truth in configuration
- Easy to maintain and version control
- Follows VictoriaMetrics best practices
- Avoids duplicate labels between config and command-line

### Scrape Relabeling

Transform labels during scrape configuration:

```yaml
scrape_configs:
  - job_name: "mock-exporter-us-east-1"
    static_configs:
      - targets: ["mock-exporter-python:2112"]
    relabel_configs:
      - source_labels: [__address__]
        target_label: instance
        replacement: "mock-exporter-us-east-1"
      - target_label: job
        replacement: "mock-exporter"
```

### Write Relabeling

Transform labels before remote write:

```yaml
remote_write:
  - url: http://vminsert-1:8480/insert/0/prometheus
    write_relabel_configs:
      - source_labels: [job]
        target_label: job
        replacement: "agent-job"
```

## System Requirements

### Minimum Requirements

| Component | CPU | Memory | Disk |
|-----------|-----|--------|------|
| vmstorage | 2 cores | 4GB | 20GB |
| vminsert | 1 core | 2GB | 1GB |
| vmselect | 1 core | 2GB | 1GB |
| vmagent | 0.5 cores | 512MB | 100MB |
| Grafana | 1 core | 2GB | 1GB |

### Recommended Production Requirements

| Component | CPU | Memory | Disk |
|-----------|-----|--------|------|
| vmstorage | 4+ cores | 16GB+ | 500GB+ SSD |
 confl vminsert | 2+ cores | 4GB+ | 10GB |
| vmselect | 2+ cores | 8GB+ | 10GB |
| vmagent | 1 core | 1GB | 1GB |

## Network Ports

| Port | Service | Description |
|------|---------|-------------|
| 3001 | Grafana | Web UI |
| 9091 | Prometheus Receiver | Query API |
| 9092 | Prometheus Writer | Admin API |
| 8427 | VictoriaMetrics vmselect | Query API (Prometheus compatible) |
| 8480 | vminsert | Remote write endpoint |
| 8481 | vmselect | Query endpoint |
| 8482 | vmstorage | Storage endpoint |
| 2112 | Mock Exporter | Metrics endpoint |

## High Availability

### vmstorage HA

- **Replication**: Data written to 2 storage nodes
- **Fault Tolerance**: Can lose 1 storage node
- **Recovery**: Automatic failover to remaining node

### vminsert HA

- **Load Balancing**: 2 vminsert nodes receive traffic
- **Stateless**: No data persistence required
- **Horizontal Scaling**: Add more replicas as needed

### vmselect HA

- **Load Balancing**: 2 vmselect nodes handle queries
- **Stateless**: No data persistence required
- **Horizontal Scaling**: Add more replicas as needed

## Security Considerations

### Authentication

- **Grafana**: Username/password (admin/admin by default)
- **Prometheus**: Basic auth or OAuth2 (configurable)
- **VictoriaMetrics**: Authentication middleware (optional)

### TLS

Enable TLS for all communications:

```yaml
# Example vmagent configuration
remote_write:
  - url: https://vminsert:8480/insert/0/prometheus
    tls_config:
      cert_file: /certs/client.crt
      key_file: /certs/client.key
      ca_file: /certs/ca.crt
```

### Network Security

- Use firewall rules to restrict access
- Configure VPC security groups
- Implement network policies (Kubernetes)

### Secrets Management

- Store passwords in secret management systems (Vault, AWS Secrets Manager)
- Use service accounts with least privilege
- Rotate credentials regularly

## Backup & Recovery

### vmstorage Backups

```bash
# Create snapshot
curl -X POST http://vmstorage:8482/snapshot/create

# List snapshots
curl http://vmstorage:8482/snapshot/list
```

### Disaster Recovery

1. **Regular Backups**: Daily snapshots of storage directories
2. **Cross-Region Replication**: Secondary cluster in different region
3. **Configuration Versioning**: All configs in version control

## Performance Tuning

### vmstorage

```bash
--storageDataPath=/vmstorage-data
--retentionPeriod=1y
--maxConcurrentInserts=16
--maxConcurrentSelects=16
--search.maxUniqueTimeseries=1000000
```

### vminsert

```bash
--maxConcurrentInserts=16
--maxInsertRequestSize=32MB
--maxRowsPerBlock=10000
```

### vmselect

```bash
--maxConcurrentSelects=16
--maxQueryLen=16384
--maxQueryDuration=30s
--cacheDataPath=/vmselect-cache
```

## Scaling Strategies

### Horizontal Scaling

Add more replicas to distribute load:
- **vminsert**: Add replicas to handle more ingestion rate
- **vmselect**: Add replicas to handle more concurrent queries
- **vmstorage**: Add replicas for more storage capacity

### Vertical Scaling

Increase resources on existing nodes:
- **CPU**: Faster processing of inserts/selects
- **Memory**: More caching and concurrent operations
- **Disk**: Larger storage capacity

## Monitoring the Architecture

### Key Metrics to Monitor

**vmstorage**:
- `vm_free_disk_space_bytes` - Available disk space
- `vm_insert_requests_total` - Ingestion rate
- `vm_rows_merge_duration_seconds` - Merge performance

**vminsert**:
- `vm_insert_requests_total` - Requests per second
- `vm_insert_request_duration_seconds` - Request latency
- `vm_promscrape_global_rows_scraped_total` - Scraped rows

**vmselect**:
- `vm_query_request_duration_seconds` - Query performance
- `vm_rows_read_per_query` - Query complexity
- `vm_cache_size_bytes` - Cache utilization

## Troubleshooting

### Common Issues

1. **vmstorage disk full**
   - Solution: Increase retention period or add storage nodes
   - Command: `curl http://vmstorage:8482/api/v1/status`

2. **vminsert queue full**
   - Solution: Increase `maxConcurrentInserts` or add vminsert replicas
   - Command: `curl http://vminsert:8480/api/v1/status`

3. **vmselect slow queries**
   - Solution: Increase `maxConcurrentSelects`, add cache, or optimize queries
   - Command: `curl http://vmselect:8481/api/v1/status`

### Debug Commands

```bash
# Check vmstorage status
curl http://vmstorage-1:8482/api/v1/status

# Check vminsert status
curl http://vminsert-1:8480/api/v1/status

# Check vmselect status
curl http://vmselect-1:8481/api/v1/status

# View logs
docker compose logs vmstorage-1
docker compose logs vminsert-1
docker compose logs vmselect-1
```

For more troubleshooting guidance, see [Troubleshooting Guide](../guides/troubleshooting.md).

## Related Documentation

- [Deployment Guide](deployment.md) - Production deployment instructions
- [Metrics Reference](../metrics/reference.md) - Comprehensive metrics documentation
- [Configuration Guide](../guides/configuration.md) - Configuration best practices

