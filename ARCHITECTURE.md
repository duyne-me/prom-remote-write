# Architecture Documentation

## Tổng quan kiến trúc

Dự án này demo 2 kiến trúc observability khác nhau:

1. **Prometheus Native**: Prometheus Writer → Prometheus Receiver
2. **VictoriaMetrics Production**: vmagent (multi-region) → vminsert → vmstorage ← vmselect

## Luồng dữ liệu chi tiết

### Flow 1: Prometheus Native

```
mock-exporter-python:2112/metrics
    ↓ (scrape)
prometheus-writer:9090
    ↓ (remote_write)
prometheus-receiver:9091
    ↓ (query)
Grafana:3000
```

**Config**: `prometheus/writer.yml`
- Scrape interval: 5s
- Remote write timeout: 30s
- Labels: cluster=dev-cluster, region=local, environment=staging

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

## VictoriaMetrics Cluster Architecture

### Components

#### vmstorage (Storage Layer)
- **2 replicas**: vmstorage-1, vmstorage-2
- **Function**: Lưu trữ time series data
- **Port**: 8482
- **Data path**: `/vmstorage-data`
- **Retention**: 1 year
- **Replication**: Data được replicate giữa 2 storage nodes

#### vminsert (Ingestion Layer)
- **2 replicas**: vminsert-1, vminsert-2
- **Function**: Nhận remote write requests, distribute data đến storage nodes
- **Port**: 8480
- **Load balancing**: Direct connection từ vmagents
- **Storage nodes**: Kết nối đến cả 2 vmstorage nodes

#### vmselect (Query Layer)
- **2 replicas**: vmselect-1, vmselect-2
- **Function**: Query time series data từ storage nodes
- **Port**: 8481
- **Load balancing**: Direct connection từ vmagents
- **Storage nodes**: Kết nối đến cả 2 vmstorage nodes



## vmagent Relabeling Mechanism

### External Labels
Labels được add cho tất cả metrics từ vmagent:

```yaml
external_labels:
  region: "us-east-1"
  cluster: "prod-us-k8s"
  environment: "production"
  datacenter: "us-east-1a"
```

### Relabel Configs
Transform labels trong scrape config:

```yaml
relabel_configs:
  - source_labels: [__address__]
    target_label: instance
    replacement: "mock-exporter-us-east-1"
  - target_label: job
    replacement: "mock-exporter"
  - target_label: region
    replacement: "us-east-1"
  - target_label: cluster
    replacement: "prod-us-k8s"
```

### Write Relabel Configs
Transform labels trước khi remote write:

```yaml
write_relabel_configs:
  - source_labels: [job]
    target_label: job
    replacement: "agent-job"
  - target_label: region
    replacement: "us-east-1"
  - target_label: cluster
    replacement: "prod-us-k8s"
```

## Production Deployment Considerations

### High Availability
- **vmstorage**: 2+ replicas với replication
- **vminsert**: 2+ replicas với load balancing
- **vmselect**: 2+ replicas với load balancing

### Scaling
- **Horizontal**: Thêm vminsert/vmselect replicas
- **Vertical**: Tăng CPU/memory cho storage nodes
- **Storage**: Tăng retention period hoặc add storage nodes

### Monitoring
- **vmstorage**: Disk usage, ingestion rate, query rate
- **vminsert**: Ingestion rate, error rate, queue size
- **vmselect**: Query rate, query duration, error rate

### Security
- **Authentication**: Basic auth hoặc OAuth2
- **TLS**: Enable TLS cho tất cả communications
- **Network**: Firewall rules, VPC security groups
- **Secrets**: Store passwords trong secret management system

### Backup & Recovery
- **vmstorage**: Regular snapshots của data directories
- **Config**: Version control cho tất cả config files
- **Disaster Recovery**: Cross-region replication

## Performance Tuning

### vmstorage
```bash
--storageDataPath=/vmstorage-data
--retentionPeriod=1y
--maxConcurrentInserts=16
--maxConcurrentSelects=16
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
```

## Troubleshooting

### Common Issues
1. **vmstorage disk full**: Tăng retention period hoặc add storage
2. **vminsert queue full**: Tăng maxConcurrentInserts
3. **vmselect slow queries**: Tăng maxConcurrentSelects

### Debug Commands
```bash
# Check vmstorage status
curl http://vmstorage-1:8482/api/v1/status

# Check vminsert status  
curl http://vminsert-1:8480/api/v1/status

# Check vmselect status
curl http://vmselect-1:8481/api/v1/status

```

### Logs
```bash
# View logs
docker compose logs vmstorage-1
docker compose logs vminsert-1
docker compose logs vmselect-1
```
