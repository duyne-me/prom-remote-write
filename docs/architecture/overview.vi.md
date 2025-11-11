# Tổng quan Kiến trúc

## Giới thiệu

Dự án demo kiến trúc monitoring production-ready, multi-environment, multi-cluster sử dụng VictoriaMetrics và vmagent. Setup mô phỏng các scenarios thực tế với:

- **Multi-Environment**: Môi trường dev và prod riêng biệt
- **Multi-Cluster**: 5 clusters độc lập across 3 AWS regions
- **High Availability**: 2 production clusters tại US East cho redundancy
- **Multi-Region**: us-east-1, eu-west-1, ap-southeast-1
- **Legacy Support**: Prometheus receiver cho external/legacy systems

## Kiến trúc Tổng thể

### 3 Luồng Dữ Liệu Chính

**Flow 1: Scraping (Luồng chính)**
```
Application → vmagent (cùng cluster) → vminsert → vmstorage
```
- 5 vmagents (1 dev + 4 prod)
- Mỗi vmagent scrape applications trong cluster của nó
- Self-scrape cho internal metrics
- Blackbox probes cho cross-region monitoring

**Flow 2: Pushing (Legacy Support)**
```
External/Legacy → prometheus-receiver → vmagent-receiver-scraper → vminsert
```
- Cho phép external Prometheus remote write vào
- vmagent-receiver-scraper forward đến VictoriaMetrics

**Flow 3: Query**
```
Grafana → vmselect → vmstorage
```
- Tất cả data trong một VictoriaMetrics cluster
- Phân biệt bằng labels: env, region, cluster

## Chi Tiết Components

### VictoriaMetrics Cluster

**Region**: us-east-1 (Centralized single-region architecture)

Tất cả VictoriaMetrics components nằm ở us-east-1. Centralized approach này có nghĩa:
- vmagents từ eu-west-1 và ap-southeast-1 remote write cross-region đến cluster này
- Cross-region latency ảnh hưởng remote write performance (monitor qua `vmagent_remotewrite_send_duration_seconds`)
- Single source of truth cho tất cả metrics across tất cả regions
- Simplified operations và querying (không cần federation)

#### vmstorage (Storage Layer)
- **Instances**: 2 (vmstorage-1, vmstorage-2)
- **Region**: us-east-1
- **Port**: 8482 (HTTP), 8400 (vminsert), 8401 (vmselect)
- **Retention**: 1 năm
- **Replication**: Data được replicate giữa 2 nodes
- **Fault Tolerance**: Có thể mất 1 node mà không mất data

#### vminsert (Ingestion Layer)
- **Instances**: 2 (vminsert-1, vminsert-2)
- **Region**: us-east-1
- **Port**: 8480 (HTTP)
- **Chức năng**: Accept remote write từ tất cả regions, distribute đến vmstorage
- **Load Balancing**: Mỗi vmagent kết nối đến vminsert cụ thể
- **Cross-Region Traffic**: Nhận remote write từ eu-west-1, ap-southeast-1 (cross-region)

#### vmselect (Query Layer)
- **Instances**: 2 (vmselect-1, vmselect-2)
- **Region**: us-east-1
- **Port**: 8481 (HTTP)
- **Chức năng**: Execute PromQL queries, aggregate từ vmstorage
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

## Label Strategy

### Standard Labels

Tất cả metrics có các labels này (từ external_labels):

| Label | Values | Mục đích |
|-------|--------|----------|
| `env` | dev, prod, monitoring | Environment isolation |
| `region` | us-east-1, eu-west-1, ap-southeast-1, local | Source region (nơi vmagent đặt) |
| `storage_region` | us-east-1 | Storage region (nơi VictoriaMetrics cluster đặt) |
| `cluster` | {region}-eks-{number}-{env} | Cluster identification |

**Phân biệt quan trọng**:
- `region`: Nơi metrics được **generate** (vmagent location)
- `storage_region`: Nơi metrics được **store** (VictoriaMetrics cluster location)
- Trong centralized architecture, tất cả metrics có `storage_region="us-east-1"` bất kể source region
- Cho phép queries như: "tất cả metrics lưu ở us-east-1" hoặc "cross-region latency analysis"

### Query Patterns

```promql
# Filter theo environment
{env="prod"}

# Filter theo region
{region="us-east-1"}

# Filter theo specific cluster
{cluster="us-east-1-eks-01-prod"}

# Filter prod trong specific region
{env="prod", region="eu-west-1"}

# HA clusters tại US East
{cluster=~"us-east-1-prod-eks-.*"}
```

## Tại Sao Kiến Trúc Này?

### Multi-Environment Separation
**Vấn đề**: Dev và prod metrics lẫn lộn  
**Giải pháp**: Môi trường riêng biệt với `env` label
- Dev: `env="dev"` - Lower priority, testing
- Prod: `env="prod"` - Production workloads
- Monitoring: `env="monitoring"` - Meta-monitoring

### Multi-Cluster cho High Availability
**Vấn đề**: Single point of failure  
**Giải pháp**: 2 clusters tại us-east-1 across khác AZs
- Nếu eks-01 (AZ-a) fails, eks-02 (AZ-b) tiếp tục hoạt động
- Mỗi cluster có vmagent độc lập
- Metrics được label rõ ràng: `cluster="us-east-1-eks-01-prod"`

### Multi-Region cho Global Reach
**Vấn đề**: High latency cho users xa datacenter  
**Giải pháp**: Deploy clusters tại 3 regions
- us-east-1: North America
- eu-west-1: Europe
- ap-southeast-1: Asia Pacific

### vmagent vs Prometheus
**Tại sao vmagent?**
- Nhẹ hơn (< 100MB memory vs 1GB+ cho Prometheus)
- Purpose-built cho scraping + remote write
- Không có local storage overhead
- Performance tốt hơn at scale
- Tối ưu cho multi-tenancy

### Centralized Storage (VictoriaMetrics)
**Tại sao central cluster?**
- Single source of truth cho tất cả metrics
- Efficient long-term storage (compression)
- Global queries across tất cả regions
- Giảm operational overhead
- HA và replication built-in

## Monitoring the Monitoring Stack

### Key Metrics Cần Watch

**vmagent Health**:
- `vmagent_remotewrite_send_duration_seconds` - Nên < 1s cho p95
- `vmagent_remotewrite_pending_bytes` - Nên thấp (< 10MB)
- `scrape_duration_seconds` - Nên < 5s cho p95

**VictoriaMetrics Health**:
- `vm_http_request_duration_seconds` - vminsert/vmselect latency
- `vm_slow_row_inserts_total` - Nên gần 0
- `vm_data_size_bytes` - Monitor disk usage growth

**Network Health**:
- `probe_success` - Nên là 1 (100% success)
- `probe_duration_seconds` - Track cross-region latency trends

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

## Troubleshooting

### vmagent Không Gửi Metrics
```bash
# Check vmagent logs
docker logs vmagent-us-east-1-eks-01-prod

# Check pending bytes (nên thấp)
curl localhost:8430/metrics | grep pending_bytes

# Check remote write errors
curl localhost:8430/metrics | grep remotewrite_errors
```

### High Remote Write Latency
1. Check network latency giữa vmagent và vminsert
2. Check vminsert CPU/Memory usage
3. Check vmstorage disk I/O
4. Cân nhắc thêm vminsert instances

### Missing Metrics trong Grafana
1. Verify vmagent đang scraping: check `up` metric
2. Verify remote write working: check vmagent logs
3. Verify labels match query: check external_labels trong config
4. Test query trực tiếp: `http://localhost:8481/select/0/prometheus`

## References

- [VictoriaMetrics Documentation](https://docs.victoriametrics.com/)
- [vmagent Documentation](https://docs.victoriametrics.com/vmagent.html)
- [Prometheus Remote Write Spec](https://prometheus.io/docs/prometheus/latest/storage/#remote-storage-integrations)
