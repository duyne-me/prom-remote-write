# Comprehensive Latency Monitoring Guide

## Overview

This guide covers all aspects of latency monitoring in the multi-environment, multi-cluster VictoriaMetrics setup. Understanding and monitoring latency is critical for maintaining a healthy observability infrastructure.

## Types of Latency

### 1. Scrape Latency
**What**: Time taken by vmagent to scrape metrics from an exporter

**Metric**: `scrape_duration_seconds`

**Source**: vmagent internal metrics (self-scrape)

**Why Important**: Indicates if exporters are responding slowly or if network issues exist

**Query Examples**:
```promql
# P95 scrape latency by cluster
histogram_quantile(0.95, sum(rate(scrape_duration_seconds_bucket[5m])) by (le, cluster))

# Scrape latency for specific cluster
scrape_duration_seconds{cluster="us-east-1-eks-01-prod"}

# Identify slow scrapes
scrape_duration_seconds > 5
```

**Dashboard**: Monitoring Stack Health

**Alert Threshold**: p95 > 5s

### 2. Remote Write Latency (MOST CRITICAL)
**What**: Time from when vmagent prepares a batch until vminsert acknowledges successful write

**Metric**: `vmagent_remotewrite_send_duration_seconds_bucket`

**Source**: vmagent internal metrics (self-scrape)

**Why Important**: 
- Direct indicator of cross-region network health
- Shows if VictoriaMetrics cluster can keep up with ingestion
- High latency = potential data loss if vmagent buffer fills

**Query Examples**:
```promql
# P95 remote write latency by cluster
histogram_quantile(0.95, sum(rate(vmagent_remotewrite_send_duration_seconds_bucket[5m])) by (le, cluster))

# Remote write latency by region
histogram_quantile(0.95, sum(rate(vmagent_remotewrite_send_duration_seconds_bucket[5m])) by (le, region))

# Compare dev vs prod latency
histogram_quantile(0.95, sum(rate(vmagent_remotewrite_send_duration_seconds_bucket[5m])) by (le, env))
```

**Dashboard**: Monitoring Stack Health

**Alert Thresholds**:
- p90 > 1s: Warning
- p95 > 2s: Critical
- p99 > 5s: Emergency

### 3. Pending Bytes (Backlog)
**What**: Bytes waiting to be sent to vminsert

**Metric**: `vmagent_remotewrite_pending_bytes`

**Why Important**: 
- Indicates network congestion or vminsert overload
- Rising value = vmagent cannot keep up
- Risk of data loss if buffer exceeds capacity

**Query Examples**:
```promql
# Pending bytes by cluster
vmagent_remotewrite_pending_bytes

# Identify clusters with backlog
vmagent_remotewrite_pending_bytes > 10000000  # > 10MB
```

**Dashboard**: Monitoring Stack Health

**Alert Threshold**: > 10MB for 5 minutes

### 4. VictoriaMetrics Ingestion Latency
**What**: Time for vminsert to process and write to vmstorage

**Metrics**: 
- `vm_http_request_duration_seconds_bucket{job="vminsert"}`
- `vm_slow_row_inserts_total`

**Query Examples**:
```promql
# vminsert request duration p95
histogram_quantile(0.95, sum(rate(vm_http_request_duration_seconds_bucket{job="vminsert"}[5m])) by (le))

# Slow inserts rate
rate(vm_slow_row_inserts_total[5m])
```

**Dashboard**: Monitoring Stack Health

**Alert Threshold**: p95 > 500ms

### 5. VictoriaMetrics Query Latency
**What**: Time for vmselect to execute queries

**Metric**: `vm_http_request_duration_seconds_bucket{job="vmselect"}`

**Query Examples**:
```promql
# vmselect query duration p95
histogram_quantile(0.95, sum(rate(vm_http_request_duration_seconds_bucket{job="vmselect"}[5m])) by (le))
```

**Dashboard**: Monitoring Stack Health

**Alert Threshold**: p95 > 2s

### 6. Cross-Region Network Latency
**What**: Network latency between regions measured by Blackbox Exporter

**Metrics**:
- `probe_duration_seconds` - Probe latency
- `probe_success` - Probe success/failure

**Source**: Blackbox Exporter (probed by vmagents)

**Query Examples**:
```promql
# Probe duration by source region
probe_duration_seconds{job="blackbox"}

# Probe success rate by source
avg(probe_success{job="blackbox"}) by (source_region) * 100

# Identify failing probes
probe_success{job="blackbox"} == 0
```

**Dashboard**: Cross-Region Latency Monitoring

**Alert Threshold**: 
- probe_success < 1 for 5 minutes
- probe_duration_seconds > 1s

## Latency Budget Example

For a production multi-region setup:

```
Total Latency Budget for Metric to appear in Grafana: 30 seconds

Breakdown:
- Scrape Latency: 1-5s (target: p95 < 3s)
- Remote Write Latency: 0.5-10s (target: p95 < 2s)
- vminsert Processing: 0.1-1s (target: p95 < 500ms)
- vmstorage Write: 0.1-1s (target: p95 < 500ms)
- Query Latency: 0.1-2s (target: p95 < 1s)
- Grafana Rendering: 0.5-2s

Target: 95% of metrics visible within 10 seconds
```

## Dashboard Guide

### Monitoring Stack Health Dashboard

This is the primary dashboard for monitoring infrastructure latency.

**Panel 1: vmagent Remote Write Latency (p90, p95, p99)**
- **Most Critical Panel**
- Shows latency distribution across percentiles
- Filter by `$cluster` variable
- **What to look for**:
  - p95 should be < 2s
  - Sudden spikes indicate network issues
  - Gradual increase indicates capacity issues

**Panel 2: vmagent Remote Write Pending Bytes**
- Shows bytes waiting to be sent
- **What to look for**:
  - Should stay near 0
  - Increasing trend = backlog building up
  - Alert if > 10MB

**Panel 3: vmagent Remote Write Success Rate**
- Shows % of successful remote write attempts
- **What to look for**:
  - Should be 100%
  - < 100% indicates errors (check vminsert health)

**Panel 4: Scrape Duration by Cluster**
- P95 scrape latency
- **What to look for**:
  - Should be < 5s
  - High values indicate slow exporters

## Troubleshooting Latency Issues

### High Remote Write Latency

**Symptoms**:
- p95 > 2s
- Pending bytes increasing
- Grafana shows delayed metrics

**Diagnosis**:
```bash
# 1. Check vmagent logs
docker logs vmagent-us-east-1-eks-01-prod | grep -i error

# 2. Check network latency to vminsert
docker exec vmagent-us-east-1-eks-01-prod ping vminsert-1

# 3. Check vminsert health
curl http://vminsert-1:8480/metrics | grep vm_http_requests_total

# 4. Check vmstorage disk I/O
docker stats vmstorage-1 vmstorage-2
```

**Solutions**:
1. **Network issue**: Check Docker network, consider adding more bandwidth
2. **vminsert overload**: Add more vminsert instances
3. **vmstorage slow**: Check disk I/O, consider faster disks (NVMe)
4. **Too many metrics**: Reduce scrape frequency or filter metrics

### High Scrape Latency

**Symptoms**:
- `scrape_duration_seconds` p95 > 5s
- Metrics delayed at source

**Diagnosis**:
```bash
# Check exporter directly
curl http://mock-exporter-python:2112/metrics

# Check vmagent scrape config
docker exec vmagent-us-east-1-eks-01-prod cat /etc/vmagent/config.yml
```

**Solutions**:
1. **Slow exporter**: Optimize exporter code
2. **Too many metrics**: Filter at scrape level
3. **Network issue**: Check container networking

### Pending Bytes Increasing

**Symptoms**:
- `vmagent_remotewrite_pending_bytes` > 10MB
- Continuously increasing

**Diagnosis**:
```promql
# Check rate of change
rate(vmagent_remotewrite_pending_bytes[5m])

# Check if remote write is failing
rate(vmagent_remotewrite_errors_total[5m])
```

**Solutions**:
1. **vminsert down**: Restart vminsert
2. **Network congestion**: Add bandwidth or reduce scrape frequency
3. **Too much data**: Increase vmagent memory or reduce metrics

## Simulating Network Latency

To test how the system behaves under various latency conditions, use the provided script:

```bash
# Add 100ms latency + 20ms jitter to EU cluster
./scripts/simulate-latency.sh add vmagent-eu-west-1-eks-01-prod 100 20

# Check latency effect in dashboard
# Monitoring Stack Health → vmagent Remote Write Latency panel

# Remove latency
./scripts/simulate-latency.sh remove vmagent-eu-west-1-eks-01-prod
```

**Test Scenarios**:

| Scenario | Latency | Jitter | Expected p95 |
|----------|---------|--------|--------------|
| Same Region | 5ms | 2ms | < 100ms |
| Cross-Region (nearby) | 50ms | 10ms | < 200ms |
| Cross-Region (far) | 150ms | 30ms | < 500ms |
| Intercontinental | 250ms | 50ms | < 1s |

See [network-latency-simulation.md](network-latency-simulation.md) for detailed guide.

## Alerting Rules

### Critical Alerts

```yaml
groups:
  - name: latency_critical
    interval: 30s
    rules:
      # Remote write latency too high
      - alert: HighRemoteWriteLatency
        expr: histogram_quantile(0.95, sum(rate(vmagent_remotewrite_send_duration_seconds_bucket[5m])) by (le, cluster)) > 2
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "High remote write latency in cluster {{ $labels.cluster }}"
          description: "P95 latency is {{ $value }}s (threshold: 2s)"
      
      # Pending bytes backlog
      - alert: RemoteWriteBacklog
        expr: vmagent_remotewrite_pending_bytes > 10000000
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Remote write backlog in cluster {{ $labels.cluster }}"
          description: "Pending bytes: {{ $value }} (threshold: 10MB)"
      
      # Scrape duration too high
      - alert: HighScrapeDuration
        expr: histogram_quantile(0.95, sum(rate(scrape_duration_seconds_bucket[5m])) by (le, cluster)) > 5
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "High scrape duration in cluster {{ $labels.cluster }}"
          description: "P95 scrape latency is {{ $value }}s (threshold: 5s)"
      
      # Cross-region probe failing
      - alert: CrossRegionProbeDown
        expr: probe_success{job="blackbox"} == 0
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Cross-region probe failed: {{ $labels.source_region }} → {{ $labels.target }}"
          description: "Network connectivity issue detected"
```

### Warning Alerts

```yaml
  - name: latency_warning
    interval: 1m
    rules:
      # vminsert slow
      - alert: VMInsertSlowRequests
        expr: histogram_quantile(0.95, sum(rate(vm_http_request_duration_seconds_bucket{job="vminsert"}[5m])) by (le)) > 0.5
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "vminsert requests are slow"
          description: "P95 request duration: {{ $value }}s (threshold: 500ms)"
      
      # vmstorage slow inserts
      - alert: VMStorageSlowInserts
        expr: rate(vm_slow_row_inserts_total[5m]) > 0
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "vmstorage experiencing slow inserts"
          description: "Slow insert rate: {{ $value }}/s"
```

## Best Practices

### 1. Set Realistic Scrape Intervals
```yaml
global:
  scrape_interval: 15s  # Good balance
  # Too low (5s): High load, more latency
  # Too high (60s): Miss short-lived events
```

### 2. Configure Adequate Remote Write Batching
vmagent automatically batches metrics. Tuning (if needed):
```yaml
# In docker-compose.yml command section
- "--remoteWrite.maxBlockSize=8MB"      # Max batch size
- "--remoteWrite.flushInterval=5s"       # Max wait before send
- "--remoteWrite.maxQueueSize=100000"    # Buffer size
```

### 3. Monitor All Latency Points
Don't just monitor one metric. Track:
- Scrape latency (source health)
- Remote write latency (network/ingestion)
- VictoriaMetrics latency (storage performance)
- Query latency (user experience)
- Cross-region network latency

### 4. Use Percentiles, Not Averages
```promql
# GOOD: Shows latency distribution
histogram_quantile(0.95, rate(scrape_duration_seconds_bucket[5m]))

# BAD: Average hides outliers
avg(scrape_duration_seconds)
```

### 5. Correlate Multiple Metrics
When debugging latency issues:
```promql
# Check all related metrics together
vmagent_remotewrite_send_duration_seconds      # Latency
vmagent_remotewrite_pending_bytes              # Backlog
vmagent_remotewrite_requests_total             # Request rate
vmagent_remotewrite_errors_total               # Errors
```

## Real-World Latency Expectations

### Scrape Latency
| Target | Expected p95 |
|--------|--------------|
| Mock Exporter (local) | < 100ms |
| Application (same pod) | < 200ms |
| Application (same node) | < 500ms |
| Application (cross-node) | < 1s |

### Remote Write Latency
| Scenario | Expected p95 |
|----------|--------------|
| vmagent → vminsert (same region) | < 500ms |
| vmagent → vminsert (cross-region, nearby) | < 2s |
| vmagent → vminsert (intercontinental) | < 5s |

### VictoriaMetrics Latency
| Component | Expected p95 |
|-----------|--------------|
| vminsert ingestion | < 200ms |
| vmselect simple query | < 500ms |
| vmselect complex query | < 5s |

### Cross-Region Network Latency
| Path | Expected p95 |
|------|--------------|
| us-east-1 ↔ us-east-1 | < 5ms |
| us-east-1 ↔ eu-west-1 | < 150ms |
| us-east-1 ↔ ap-southeast-1 | < 250ms |
| eu-west-1 ↔ ap-southeast-1 | < 300ms |

## Using the Dashboards

### Dashboard: Monitoring Stack Health

**Step 1**: Open dashboard in Grafana  
URL: `http://localhost:3001/d/monitoring-stack-health`

**Step 2**: Select cluster(s) to monitor
- Variable at top: `$cluster`
- Default: All clusters
- Select specific cluster for detailed view

**Step 3**: Analyze key panels

**Panel: vmagent Remote Write Latency**
- Green line (p90): Should be < 1s
- Yellow line (p95): Should be < 2s
- Red line (p99): May spike but average < 5s
- **Action if high**: Check network, check vminsert health

**Panel: Pending Bytes**
- Should be flat line near 0
- Spikes OK if they recover quickly
- Increasing trend = problem
- **Action if increasing**: Check remote write errors, check vminsert capacity

**Panel: Scrape Duration**
- Shows how long scrapes take
- High values indicate slow exporters
- **Action if high**: Optimize exporter, reduce metrics

### Dashboard: Cross-Region Latency Monitoring

**Panel: Blackbox Probe Duration**
- Shows actual network latency between regions
- Baseline: Same-region probes (lowest latency)
- Cross-region: Higher but should be stable
- **Action if high**: Check network routing, ISP issues

**Panel: Probe Success Rate**
- Should be 100% (gauge shows green)
- < 100% indicates network connectivity issues
- **Action if < 100%**: Check firewalls, DNS, network routing

## Advanced Scenarios

### Scenario 1: Gradual Latency Increase

**Observation**: Remote write p95 slowly increasing from 500ms to 2s over days

**Possible Causes**:
1. vmstorage disk filling up (slower writes)
2. Increasing metric cardinality (more unique label combinations)
3. vminsert instance degradation

**Investigation**:
```promql
# Check storage size growth
rate(vm_data_size_bytes[1d])

# Check metric cardinality
count(count by (__name__, job) (up))

# Check vminsert request rate
rate(vm_http_requests_total{job="vminsert"}[1h])
```

### Scenario 2: Sudden Latency Spike

**Observation**: Remote write p95 suddenly jumps to 10s

**Possible Causes**:
1. Network issue (packet loss, routing change)
2. vminsert restart/deployment
3. vmstorage node failure

**Investigation**:
```bash
# Check container restarts
docker ps -a | grep vminsert

# Check network latency
docker exec vmagent-us-east-1-eks-01-prod ping -c 5 vminsert-1

# Check vmstorage health
curl http://vmstorage-1:8482/metrics | grep vm_rows_inserted
```

### Scenario 3: Regional Latency Difference

**Observation**: EU cluster has 3x higher latency than US clusters

**Expected Behavior**: Cross-region network latency is higher

**Investigation**:
```promql
# Compare remote write latency by region
histogram_quantile(0.95, sum(rate(vmagent_remotewrite_send_duration_seconds_bucket[5m])) by (le, region))

# Check if EU vmagent talks to different vminsert
vmagent_remotewrite_requests_total{region="eu-west-1"}
```

**Solutions**:
- Deploy vminsert in EU region (federated setup)
- Accept higher latency as acceptable trade-off
- Use `-remoteWrite.queues` flag to increase parallelism

## Optimizations

### Reduce Remote Write Latency

1. **Increase Parallelism**:
```yaml
# docker-compose.yml
command:
  - "--remoteWrite.queues=4"  # Default: 1
```

2. **Tune Batch Sizes**:
```yaml
command:
  - "--remoteWrite.maxBlockSize=16MB"  # Larger batches (default: 8MB)
  - "--remoteWrite.flushInterval=3s"   # Send more frequently (default: 5s)
```

3. **Use Compression**:
```yaml
command:
  - "--remoteWrite.compress=true"  # Default: enabled
```

### Reduce Scrape Latency

1. **Optimize Exporter**:
- Reduce number of metrics exposed
- Use metric caching
- Optimize label cardinality

2. **Adjust Timeout**:
```yaml
scrape_configs:
  - job_name: "slow-exporter"
    scrape_timeout: 30s  # Default: 10s
```

## Metrics Retention

For latency metrics, consider different retention policies:

```yaml
# Short retention for high-res data
-retentionPeriod=90d  # For scrape_duration_seconds

# Medium retention for aggregated data
-retentionPeriod=1y   # For remote write latency percentiles

# Long retention for SLOs
-retentionPeriod=2y   # For monthly latency SLOs
```

## Conclusion

Effective latency monitoring requires:
1. **Comprehensive Coverage**: Monitor all latency points
2. **Right Metrics**: Use histograms, calculate percentiles
3. **Proactive Alerts**: Alert before users notice
4. **Regular Review**: Weekly review of latency trends
5. **Continuous Optimization**: Always improving

Key takeaway: **Remote write latency is the most critical metric** for multi-region monitoring infrastructure. Focus your optimization efforts there first.

## Additional Resources

- [Network Latency Simulation Guide](network-latency-simulation.md)
- [VictoriaMetrics Performance Tuning](https://docs.victoriametrics.com/FAQ.html#how-to-optimize-performance)
- [vmagent Tuning](https://docs.victoriametrics.com/vmagent.html#tuning)

