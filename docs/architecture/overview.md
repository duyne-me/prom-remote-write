# Architecture Overview

## Introduction

This project demonstrates a production-ready, multi-environment, multi-cluster monitoring architecture using VictoriaMetrics and vmagent. The setup simulates real-world scenarios with:

- **Multi-Environment**: Separate dev and prod environments
- **Multi-Cluster**: 5 independent clusters across 3 AWS regions
- **High Availability**: 2 production clusters in US East for redundancy
- **Multi-Region**: us-east-1, eu-west-1, ap-southeast-1
- **Legacy Support**: Prometheus receiver for external/legacy systems

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                    MOCK EXPORTER (Python)                           │
│                   340+ Production Metrics                           │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
        ┌──────────────────────┼──────────────────────┐
        │                      │                      │
        ▼                      ▼                      ▼
┌───────────────┐    ┌───────────────┐    ┌───────────────┐
│  Dev Env      │    │  Prod Env     │    │  Prod Env     │
│  ap-sg-1      │    │  us-east-1    │    │  eu-west-1    │
│               │    │  (HA: 2 cls)  │    │  ap-sg-1      │
└───────┬───────┘    └───────┬───────┘    └───────┬───────┘
        │                    │                    │
        │    5 vmagent Instances                 │
        │    (self-scrape + blackbox probes)     │
        │                    │                    │
        └────────────────────┼────────────────────┘
                             │
                    ┌────────┴────────┐
                    ▼                 ▼
            ┌──────────────┐  ┌──────────────┐
            │  vminsert-1  │  │  vminsert-2  │
            └──────┬───────┘  └──────┬───────┘
                   │                 │
        ┌──────────┴─────────────────┴──────────┐
        │                                        │
        ▼                                        ▼
┌──────────────┐                        ┌──────────────┐
│ vmstorage-1  │◄──────────────────────►│ vmstorage-2  │
└──────┬───────┘      Replication       └──────┬───────┘
       │                                        │
       └────────────────┬───────────────────────┘
                        │
            ┌───────────┴───────────┐
            ▼                       ▼
    ┌──────────────┐        ┌──────────────┐
    │  vmselect-1  │        │  vmselect-2  │
    └──────┬───────┘        └──────────────┘
           │
           ▼
    ┌──────────────┐
    │   Grafana    │
    │  Port 3001   │
    └──────────────┘

LEGACY PUSH FLOW (Separate):
┌──────────────────┐
│ External/Legacy  │
│    Prometheus    │
└────────┬─────────┘
         │ remote_write
         ▼
┌──────────────────────┐
│ prometheus-receiver  │
│    Port 9091         │
└────────┬─────────────┘
         │ scraped by
         ▼
┌────────────────────────┐
│ vmagent-receiver-      │
│    scraper             │
└────────┬───────────────┘
         │
         └──────► vminsert-1
```

## Component Details

### VictoriaMetrics Cluster

**Region**: us-east-1 (Centralized single-region architecture)

All VictoriaMetrics components are located in us-east-1. This centralized approach means:
- vmagents from eu-west-1 and ap-southeast-1 remote write cross-region to this cluster
- Cross-region latency affects remote write performance (monitored via `vmagent_remotewrite_send_duration_seconds`)
- Single source of truth for all metrics across all regions
- Simplified operations and querying (no federation needed)

#### vmstorage (Storage Layer)
- **Instances**: 2 (vmstorage-1, vmstorage-2)
- **Region**: us-east-1
- **Port**: 8482 (HTTP), 8400 (vminsert), 8401 (vmselect)
- **Retention**: 1 year
- **Replication**: Data replicated between both nodes
- **Fault Tolerance**: Can lose 1 node without data loss

#### vminsert (Ingestion Layer)
- **Instances**: 2 (vminsert-1, vminsert-2)
- **Region**: us-east-1
- **Port**: 8480 (HTTP)
- **Function**: Accept remote write from all regions, distribute to vmstorage
- **Load Balancing**: vmagents connect to specific vminsert instance
- **Cross-Region Traffic**: Receives remote write from eu-west-1, ap-southeast-1 (cross-region)

#### vmselect (Query Layer)
- **Instances**: 2 (vmselect-1, vmselect-2)
- **Region**: us-east-1
- **Port**: 8481 (HTTP)
- **Function**: Execute PromQL queries, aggregate from vmstorage
- **Performance**: Cached queries, parallel execution

### vmagent Instances

#### Development Environment
**Cluster**: `ap-southeast-1-eks-01-dev`
- **Environment**: dev
- **Region**: ap-southeast-1 (Singapore)
- **AZ**: ap-southeast-1a
- **Remote Write**: vminsert-1
- **Port**: 8429

#### Production Environment - US East (High Availability)

**Cluster 1**: `us-east-1-eks-01-prod`
- **Environment**: prod
- **Region**: us-east-1 (N. Virginia)
- **AZ**: us-east-1a
- **Remote Write**: vminsert-1
- **Port**: 8430

**Cluster 2**: `us-east-1-eks-02-prod`
- **Environment**: prod
- **Region**: us-east-1 (N. Virginia)
- **AZ**: us-east-1b
- **Remote Write**: vminsert-2
- **Port**: 8431

#### Production Environment - Europe

**Cluster**: `eu-west-1-eks-01-prod`
- **Environment**: prod
- **Region**: eu-west-1 (Ireland)
- **AZ**: eu-west-1a
- **Remote Write**: vminsert-1
- **Port**: 8432

#### Production Environment - Asia Pacific

**Cluster**: `ap-southeast-1-eks-01-prod`
- **Environment**: prod
- **Region**: ap-southeast-1 (Singapore)
- **AZ**: ap-southeast-1a
- **Remote Write**: vminsert-2
- **Port**: 8433

### Legacy Support Components

#### prometheus-receiver
- **Port**: 9091
- **Function**: Accept remote write from external Prometheus
- **Flag**: `--web.enable-remote-write-receiver`
- **Retention**: 1h (short, data forwarded by vmagent-receiver-scraper)

#### vmagent-receiver-scraper
- **Port**: 8434
- **Function**: Scrape prometheus-receiver, forward to VictoriaMetrics
- **Labels**: env=prod, region=us-east-1, cluster=us-east-1-eks-01-prod-legacy (legacy system)
- **Remote Write**: vminsert-1

### Blackbox Exporter
- **Port**: 9115
- **Function**: Network probes for cross-region latency monitoring
- **Module**: http_2xx (HTTP GET probes, timeout: 10s for cross-region)
- **Probed by**: All 5 vmagents
- **Cross-Region Probing**: Each vmagent probes endpoints in OTHER regions (not same region)
- **Labels**: `source_region`, `target_region` for cross-region tracking
- **Metrics**: `probe_duration_seconds`, `probe_success`

## Data Flow Details

### Flow 1: Scraping (Main Flow)

**Step-by-Step**:
1. **Application** exposes metrics at `/metrics` endpoint
2. **vmagent** scrapes:
   - Application metrics (mock-exporter:2112)
   - Self metrics (localhost:8429)
   - Blackbox probes (blackbox-exporter:9115)
3. **vmagent** applies `external_labels` to all metrics:
   - env, region, cluster
4. **vmagent** batches metrics and remote write to **vminsert**
5. **vminsert** distributes metrics to **vmstorage-1** and **vmstorage-2**
6. **vmstorage** stores compressed time series data
7. **Grafana** queries via **vmselect**
8. **vmselect** aggregates results from both vmstorage nodes

### Flow 2: Pushing (Legacy Support)

**Step-by-Step**:
1. **External Prometheus** remote writes to **prometheus-receiver:9091/api/v1/write**
2. **prometheus-receiver** accepts and temporarily stores metrics
3. **vmagent-receiver-scraper** scrapes **prometheus-receiver:9091/metrics**
4. **vmagent-receiver-scraper** adds labels (env=monitoring, etc.)
5. **vmagent-receiver-scraper** remote writes to **vminsert-1**
6. Flow continues same as Flow 1 from vminsert onwards

## Label Strategy

### Standard Labels

All metrics have these labels (from external_labels):

| Label | Values | Purpose |
|-------|--------|---------|
| `env` | dev, prod, monitoring | Environment isolation |
| `region` | us-east-1, eu-west-1, ap-southeast-1, local | Source region (where vmagent is located) |
| `storage_region` | us-east-1 | Storage region (where VictoriaMetrics cluster is located) |
| `cluster` | {region}-eks-{number}-{env} | Cluster identification |

**Key Distinction**:
- `region`: Where metrics are **generated** (vmagent location)
- `storage_region`: Where metrics are **stored** (VictoriaMetrics cluster location)
- In centralized architecture, all metrics have `storage_region="us-east-1"` regardless of source region
- This enables queries like: "all metrics stored in us-east-1" or "cross-region latency analysis"

### Query Patterns

```promql
# Filter by environment
{env="prod"}

# Filter by region
{region="us-east-1"}

# Filter by specific cluster
{cluster="us-east-1-eks-01-prod"}

# Filter prod in specific region
{env="prod", region="eu-west-1"}

# HA clusters in US East
{cluster=~"us-east-1-prod-eks-.*"}
```

## High Availability Design

### vmstorage HA
- **Replication**: All data written to 2 storage nodes
- **Fault Tolerance**: Can lose 1 node
- **Recovery**: Automatic, no data loss

### vminsert Load Balancing
- **Strategy**: Static assignment per vmagent
- **Distribution**: 3 vmagents → vminsert-1, 2 vmagents → vminsert-2
- **Failover**: Manual reconfiguration required

### US East HA
- **2 Production Clusters**: us-east-1-eks-01-prod, us-east-1-eks-02-prod
- **Different AZs**: us-east-1a, us-east-1b
- **Independent vmagents**: Each cluster has own vmagent
- **Purpose**: Simulate Kubernetes multi-cluster HA

## Scalability

### Horizontal Scaling

**vmagent**: Add more clusters/regions
```yaml
# New cluster in sa-east-1
vmagent-sa-east-1-prod-eks-01:
  external_labels:
    env: "prod"
    region: "sa-east-1"
    cluster: "sa-east-1-prod-eks-01"
```

**vminsert/vmselect**: Add more instances for higher throughput
```yaml
vminsert-3:
  command:
    - "--storageNode=vmstorage-1:8400"
    - "--storageNode=vmstorage-2:8400"
```

**vmstorage**: Add more nodes for increased storage capacity
- Update all vminsert instances with new storage node
- Update all vmselect instances with new storage node

### Vertical Scaling
- Increase CPU/Memory for vminsert (handle more ingestion)
- Increase Memory for vmselect (faster queries)
- Increase Disk for vmstorage (more retention)

## Monitoring the Monitoring Stack

### Key Metrics to Watch

**vmagent Health**:
- `vmagent_remotewrite_send_duration_seconds` - Should be < 1s for p95
- `vmagent_remotewrite_pending_bytes` - Should stay low (< 10MB)
- `scrape_duration_seconds` - Should be < 5s for p95

**VictoriaMetrics Health**:
- `vm_http_request_duration_seconds` - vminsert/vmselect latency
- `vm_slow_row_inserts_total` - Should be near 0
- `vm_data_size_bytes` - Monitor disk usage growth

**Network Health**:
- `probe_success` - Should be 1 (100% success)
- `probe_duration_seconds` - Track cross-region latency trends

### Alerting Rules

```yaml
groups:
  - name: vmagent
    rules:
      - alert: HighRemoteWriteLatency
        expr: histogram_quantile(0.95, rate(vmagent_remotewrite_send_duration_seconds_bucket[5m])) > 2
        for: 5m
        annotations:
          summary: "vmagent remote write latency too high"
      
      - alert: RemoteWritePendingBytes
        expr: vmagent_remotewrite_pending_bytes > 10000000
        for: 5m
        annotations:
          summary: "vmagent has too many pending bytes"
  
  - name: victoriametrics
    rules:
      - alert: VMStorageDiskFull
        expr: vm_free_disk_space_bytes / vm_data_size_bytes < 0.1
        for: 5m
        annotations:
          summary: "VMStorage disk < 10% free"
```

## Network Architecture

### Internal Communication (Docker Network)

All services run on `promnet` bridge network:
- **Mock Exporter**: mock-exporter-python:2112
- **vmagents**: Each accessible on localhost:8429 internally
- **prometheus-receiver**: prometheus-receiver:9091
- **blackbox-exporter**: blackbox-exporter:9115
- **VictoriaMetrics**: vminsert/vmselect/vmstorage use internal ports

### External Access

- **Grafana**: localhost:3001 (mapped from container:3000)
- **vmagent metrics**: localhost:8429-8434 (each vmagent exposed)
- **Prometheus Receiver**: localhost:9091 (for external remote write)
- **Blackbox Exporter**: localhost:9115 (for debugging probes)

## Why This Architecture?

### Multi-Environment Separation
**Problem**: Dev and prod metrics mixed together  
**Solution**: Separate environments with `env` label
- Dev: `env="dev"` - Lower priority, testing
- Prod: `env="prod"` - Production workloads
- Monitoring: `env="monitoring"` - Meta-monitoring

### Multi-Cluster for High Availability
**Problem**: Single point of failure  
**Solution**: 2 clusters in us-east-1 across different AZs
- If eks-01 (AZ-a) fails, eks-02 (AZ-b) continues
- Each cluster has independent vmagent
- Metrics clearly labeled: `cluster="us-east-1-eks-01-prod"`

### Multi-Region for Global Reach
**Problem**: High latency for users far from datacenter  
**Solution**: Deploy clusters in 3 regions
- us-east-1: North America
- eu-west-1: Europe
- ap-southeast-1: Asia Pacific

### vmagent vs Prometheus
**Why vmagent?**
- Lightweight (< 100MB memory vs 1GB+ for Prometheus)
- Purpose-built for scraping + remote write
- No local storage overhead
- Better performance at scale
- Optimized for multi-tenancy

### Centralized Storage (VictoriaMetrics)
**Why central cluster?**
- Single source of truth for all metrics
- Efficient long-term storage (compression)
- Global queries across all regions
- Reduced operational overhead
- HA and replication built-in

## Comparison with Other Architectures

### vs. Prometheus Federation
**This setup**:
- vmagent scrapes → remote write → VictoriaMetrics
- No federation needed, labels for filtering
- Better performance, simpler

**Prometheus Federation**:
- Multiple Prometheus → federate to central Prometheus
- Complex configuration, label conflicts
- Higher resource usage

### vs. Thanos
**This setup**:
- vmagent + VictoriaMetrics
- Simpler architecture
- Lower operational cost

**Thanos**:
- Prometheus + Thanos sidecars + object storage
- More complex, higher costs
- Better for long-term storage at massive scale

### vs. Cortex
**This setup**:
- VictoriaMetrics (simpler)
- Single binary deployments
- Lower learning curve

**Cortex**:
- Multi-tenant by design
- More microservices
- Kubernetes-native

## Production Recommendations

### Minimum Requirements (per component)

| Component | CPU | Memory | Disk |
|-----------|-----|--------|------|
| vmagent | 0.5 cores | 512MB | 1GB |
| vminsert | 1 core | 2GB | 5GB |
| vmselect | 1 core | 2GB | 5GB |
| vmstorage | 2 cores | 4GB | 100GB SSD |
| Grafana | 1 core | 1GB | 5GB |

### Production Requirements (high load)

| Component | CPU | Memory | Disk |
|-----------|-----|--------|------|
| vmagent | 1 core | 1GB | 5GB |
| vminsert | 4 cores | 8GB | 10GB |
| vmselect | 4 cores | 16GB | 10GB |
| vmstorage | 8 cores | 32GB | 1TB NVMe SSD |
| Grafana | 2 cores | 4GB | 20GB |

### Network Requirements
- **Bandwidth**: 100Mbps+ between vmagent and vminsert
- **Latency**: < 100ms recommended for remote write
- **Reliability**: 99.9%+ uptime for vminsert/vmstorage

## Security Considerations

### Authentication
- **Grafana**: Enable authentication (currently anonymous for demo)
- **VictoriaMetrics**: Add `-httpAuth.*` flags for basic auth
- **prometheus-receiver**: Add authentication for external writes

### Network Security
- **Firewall**: Restrict vminsert ports to known vmagent IPs only
- **TLS**: Enable HTTPS for all external endpoints
- **mTLS**: Consider mutual TLS for vmagent → vminsert

### Data Privacy
- **Label Scrubbing**: Remove sensitive labels before remote write
- **Metric Filtering**: Drop unnecessary metrics to reduce storage
- **Retention Policy**: Set appropriate retention (1y default)

## Troubleshooting

### vmagent Not Sending Metrics
```bash
# Check vmagent logs
docker logs vmagent-us-east-1-eks-01-prod

# Check pending bytes (should be low)
curl localhost:8430/metrics | grep pending_bytes

# Check remote write errors
curl localhost:8430/metrics | grep remotewrite_errors
```

### High Remote Write Latency
1. Check network latency between vmagent and vminsert
2. Check vminsert CPU/Memory usage
3. Check vmstorage disk I/O
4. Consider adding more vminsert instances

### Missing Metrics in Grafana
1. Verify vmagent is scraping: check `up` metric
2. Verify remote write working: check vmagent logs
3. Verify labels match query: check external_labels in config
4. Test query directly in VictoriaMetrics: `http://localhost:8481/select/0/prometheus`

### Blackbox Probes Not Working
```bash
# Test blackbox directly
curl 'http://localhost:9115/probe?target=http://mock-exporter-python:2112&module=http_2xx'

# Check vmagent blackbox scrape config
docker exec vmagent-us-east-1-eks-01-prod cat /etc/vmagent/config.yml
```

## Next Steps

1. **Add Real Applications**: Replace mock-exporter with actual services
2. **Configure Alerting**: Set up alertmanager with notification channels
3. **Add Recording Rules**: Pre-aggregate frequently used queries
4. **Enable Authentication**: Secure all endpoints
5. **Add More Regions**: Expand to sa-east-1, ap-northeast-1, etc.
6. **Implement Network Latency**: Use `tc` to simulate realistic cross-region latency
7. **Scale VictoriaMetrics**: Add more vmstorage/vminsert as load increases

## References

- [VictoriaMetrics Documentation](https://docs.victoriametrics.com/)
- [vmagent Documentation](https://docs.victoriametrics.com/vmagent.html)
- [Prometheus Remote Write Spec](https://prometheus.io/docs/concepts/remote_write_spec/)
- [Blackbox Exporter](https://github.com/prometheus/blackbox_exporter)
