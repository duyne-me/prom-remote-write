# Grafana Dashboard Guide

This guide explains how to use each of the 4 pre-configured Grafana dashboards.

## Dashboard 1: Global Infrastructure Overview

**URL**: `http://localhost:3001/d/global-infrastructure`

**Purpose**: High-level overview of entire monitoring infrastructure

**Target Audience**: SRE, Engineering Managers, Operations

### Key Panels

#### Total Metrics Ingestion Rate
- **Type**: Stat panel
- **Metric**: `sum(rate(vmagent_remotewrite_samples_total[5m]))`
- **What it shows**: Total metrics/sec being ingested across ALL clusters
- **Expected value**: 1000-10000 samples/sec (depends on scrape interval)
- **Alert if**: Drops to 0 or significantly decreases

#### Metrics Ingestion Rate by Region
- **Type**: Time series graph
- **Metric**: `sum(rate(vmagent_remotewrite_samples_total[5m])) by (region)`
- **What it shows**: How metrics are distributed across regions
- **Use case**: Identify regional load imbalance

#### Metrics Ingestion Rate by Environment
- **Type**: Time series graph
- **Metric**: `sum(rate(vmagent_remotewrite_samples_total[5m])) by (env)`
- **What it shows**: Dev vs Prod metrics distribution
- **Use case**: Ensure dev environment not overwhelming prod

#### Cluster Status - Mock Exporter Targets
- **Type**: Table
- **Metric**: `up{job="mock-exporter"}`
- **What it shows**: Which exporters are up/down per cluster
- **Color coding**: Green = UP (1), Red = DOWN (0)
- **Alert if**: Any cluster shows DOWN

#### Active vmagent Instances
- **Type**: Stat panel
- **Metric**: `count(up{job="vmagent-self"} == 1)`
- **Expected value**: 5 (all vmagents running)
- **Alert if**: < 5

#### Total Clusters
- **Type**: Stat panel
- **Metric**: `count(count by (cluster) (up{job="mock-exporter"}))`
- **Expected value**: 5
- **Alert if**: < 5

### When to Use This Dashboard
- Daily health check of monitoring infrastructure
- Incident response: Quick overview of system status
- Capacity planning: Track ingestion growth
- After deployments: Verify all clusters are active

---

## Dashboard 2: Application Performance (RED)

**URL**: `http://localhost:3001/d/application-performance`

**Purpose**: Monitor application performance using RED method (Rate, Errors, Duration)

**Target Audience**: Developers, Application Owners, SRE

### Variables

#### $env (Environment)
- **Type**: Single select dropdown
- **Values**: dev, prod
- **Purpose**: Filter metrics by environment
- **Default**: prod

#### $cluster (Cluster)
- **Type**: Single select dropdown
- **Values**: Dynamic based on selected `$env`
- **Purpose**: Drill down to specific cluster
- **Examples**: 
  - If env=prod: us-east-1-prod-eks-01, us-east-1-prod-eks-02, etc.
  - If env=dev: ap-southeast-1-dev-eks-01

### Key Panels

#### Request Rate (RED - Rate)
- **Metric**: `sum(rate(http_requests_total{env="$env", cluster="$cluster"}[5m])) by (service, method)`
- **What it shows**: Requests per second by service and HTTP method
- **Use case**: Identify traffic patterns, detect traffic drops

#### Current Error Rate % (RED - Errors)
- **Type**: Gauge
- **Metric**: `sum(rate(http_requests_total{env="$env", cluster="$cluster", status_code=~"5.."}[5m])) / sum(rate(http_requests_total{env="$env", cluster="$cluster"}[5m])) * 100`
- **What it shows**: Real-time error rate percentage
- **Thresholds**:
  - Green: < 1%
  - Yellow: 1-5%
  - Red: > 5%
- **Alert if**: > 5% for 5 minutes

#### Total Request Rate
- **Type**: Stat panel
- **Metric**: Total requests/sec for selected cluster
- **Use case**: Quick glance at traffic volume

#### Error Rate Over Time by Service
- **Metric**: Error rate calculated per service
- **What it shows**: Which services are experiencing errors
- **Use case**: Identify problematic services

#### Request Latency Distribution (RED - Duration)
- **Type**: Heatmap
- **Metric**: `sum(rate(http_request_duration_seconds_bucket{env="$env", cluster="$cluster"}[5m])) by (le)`
- **What it shows**: Latency distribution over time
- **Color**: Dark = low frequency, Bright = high frequency
- **Use case**: Identify latency outliers, see latency patterns

#### Request Latency Percentiles (p50, p95, p99)
- **Type**: Time series graph
- **Metrics**: Histogram quantiles at 50th, 95th, 99th percentiles
- **What it shows**: Latency trends
- **Thresholds**:
  - p50 (green): Should be < 100ms
  - p95 (yellow): Should be < 500ms
  - p99 (red): Should be < 2s
- **Alert if**: p95 > 1s

#### Top 10 Slowest Endpoints
- **Type**: Table
- **Metric**: Top 10 endpoints ranked by p95 latency
- **What it shows**: Which API endpoints need optimization
- **Use case**: Prioritize performance optimization efforts

### How to Use

1. **Select Environment**: Choose dev or prod from dropdown
2. **Select Cluster**: Choose specific cluster to analyze
3. **Analyze RED metrics**:
   - Rate: Is traffic normal?
   - Errors: Are error rates acceptable?
   - Duration: Are response times good?
4. **Drill down**: Click on slow endpoints in table to investigate

### Common Workflows

**Workflow 1: Daily Performance Check**
1. Select env=prod
2. Select cluster=us-east-1-prod-eks-01
3. Check current error rate (should be < 1%)
4. Check p95 latency (should be < 500ms)
5. Review top 10 slowest endpoints

**Workflow 2: Debugging High Latency**
1. Observe high p95 latency in graph
2. Check heatmap for latency distribution
3. Identify if it's a few slow requests (outliers) or widespread
4. Check "Top 10 Slowest Endpoints" table
5. Investigate those specific endpoints in logs/traces

**Workflow 3: Comparing Clusters**
1. Note metrics for cluster A
2. Switch $cluster variable to cluster B
3. Compare request rate, error rate, latency
4. Identify if issue is cluster-specific or global

---

## Dashboard 3: Monitoring Stack Health

**URL**: `http://localhost:3001/d/monitoring-stack-health`

**Purpose**: Ensure the monitoring infrastructure itself is healthy

**Target Audience**: SRE, Platform Engineers

### Variables

#### $cluster
- **Type**: Multi-select dropdown with "All" option
- **Default**: All
- **Purpose**: Filter vmagent metrics by cluster(s)

### Key Panels

#### vmagent Remote Write Latency (p90, p95, p99)
- **MOST IMPORTANT PANEL**
- **Metrics**: Histogram quantiles of remote write latency
- **What it shows**: How long it takes vmagent to send metrics to vminsert
- **Expected values**:
  - p90: < 500ms
  - p95: < 1s
  - p99: < 2s
- **Alert thresholds**:
  - Warning: p95 > 1s
  - Critical: p95 > 2s
- **What to check if high**:
  - Network latency between vmagent and vminsert
  - vminsert CPU/memory usage
  - vmstorage disk I/O

#### vmagent Remote Write Pending Bytes
- **Metric**: `vmagent_remotewrite_pending_bytes`
- **What it shows**: Bytes waiting to be sent (backlog)
- **Expected value**: Near 0, small spikes OK
- **Alert if**: > 10MB for 5 minutes
- **Indicates**:
  - Growing: vmagent can't keep up (network slow or vminsert overloaded)
  - Flat at 0: Healthy
  - Oscillating: Normal batching behavior

#### vmagent Remote Write Success Rate
- **Metric**: Success rate calculation
- **Expected value**: 100%
- **Alert if**: < 99%
- **Indicates errors**: Network failures, vminsert down, authentication issues

#### Scrape Duration by Cluster
- **Metric**: `histogram_quantile(0.95, sum(rate(scrape_duration_seconds_bucket[5m])) by (le, cluster))`
- **What it shows**: How long vmagent takes to scrape exporters
- **Expected value**: p95 < 2s
- **Alert if**: > 5s
- **Indicates**: Slow exporter or network issues

#### VictoriaMetrics Components Health Table
- **Metric**: `up{job=~"vminsert|vmselect|vmstorage"}`
- **What it shows**: Which VM components are up/down
- **Expected**: All components UP (green background)
- **Alert if**: Any component DOWN

#### VMStorage Disk Usage
- **Metric**: `vm_data_size_bytes`
- **What it shows**: Storage growth over time
- **Use case**: Capacity planning, predict when disk will fill

#### VictoriaMetrics Request Duration
- **Metrics**: vminsert and vmselect p95 latency
- **Expected values**:
  - vminsert: < 200ms
  - vmselect: < 1s (depends on query complexity)
- **Alert if**: vminsert > 500ms

#### VMStorage Slow Inserts Rate
- **Metric**: `rate(vm_slow_row_inserts_total[5m])`
- **Expected value**: 0 or near 0
- **Alert if**: > 10/sec
- **Indicates**: Disk I/O issues or memory pressure

### When to Use This Dashboard
- Continuous monitoring (keep open on NOC screen)
- Investigating "metrics not appearing" issues
- Before/after infrastructure changes
- Capacity planning reviews

---

## Dashboard 4: Cross-Region Latency Monitoring

**URL**: `http://localhost:3001/d/cross-region-latency`

**Purpose**: Monitor network latency and connectivity between regions

**Target Audience**: Network Engineers, SRE, DevOps

### Key Panels

#### Blackbox Probe Duration by Source Region
- **Metric**: `probe_duration_seconds{job="blackbox"}`
- **What it shows**: Actual network latency from each region
- **Expected values**:
  - Same region: < 5ms
  - Cross-region (nearby): 50-150ms
  - Intercontinental: 150-300ms
- **Use case**: Establish latency baselines, detect routing issues

#### Overall Probe Success Rate
- **Type**: Gauge
- **Metric**: `avg(probe_success{job="blackbox"}) * 100`
- **Expected value**: 100% (green)
- **Alert if**: < 99%
- **Indicates**: Network connectivity issues, firewall blocking

#### Total Active Probes
- **Metric**: `count(probe_success{job="blackbox"})`
- **Expected value**: Number of vmagents × probes per agent
- **Alert if**: Decreases (probes stopped working)

#### Cross-Region Probe Latency Heatmap
- **Type**: Heatmap
- **What it shows**: Latency distribution across regions over time
- **Use case**: Visual representation of latency patterns

#### Top 10 Slowest Probe Paths
- **Type**: Table
- **Metric**: Top 10 probes sorted by duration
- **What it shows**: Which region→target paths are slowest
- **Use case**: Identify problematic network paths

#### Probe Success Rate by Source Region
- **Metric**: Success rate calculated per source region
- **Expected value**: 100% for all regions
- **Alert if**: Any region < 99%

#### Network Latency Trends (24h)
- **Time range**: Last 24 hours
- **What it shows**: Historical latency trends
- **Use case**: Identify patterns, compare to previous days

### When to Use This Dashboard
- Investigating network issues
- After network infrastructure changes
- Capacity planning for multi-region expansion
- SLA verification for cross-region connectivity

---

## General Tips

### Dashboard Auto-Refresh
All dashboards auto-refresh every 10 seconds. To change:
- Click time picker (top right)
- Select refresh interval
- Options: 5s, 10s, 30s, 1m, 5m

### Time Range Selection
- Default: Last 1 hour (Last 24h for cross-region dashboard)
- Quick ranges: 5m, 15m, 1h, 6h, 24h, 7d
- Custom: Click time picker and select custom range

### Sharing Dashboards
1. Click share icon (top right)
2. Copy link
3. Link includes current time range and variable selections

### Exporting Data
From any panel:
1. Click panel title → More → Inspect → Data
2. Download as CSV
3. Use for reporting or analysis in Excel/Python

### Creating Alerts
From any panel:
1. Click panel title → More → New alert rule
2. Define condition (e.g., value > threshold)
3. Configure notification channel
4. Save

## Dashboard Combinations for Common Tasks

### Task: Investigate Production Incident

1. **Start**: Global Infrastructure Overview
   - Verify which clusters are affected
   - Check if ingestion rate dropped

2. **Next**: Application Performance (RED)
   - Select affected cluster
   - Check error rate and latency
   - Identify slow endpoints

3. **Then**: Monitoring Stack Health
   - Verify vmagent is healthy
   - Check if remote write latency spiked
   - Verify VictoriaMetrics components are up

4. **Finally**: Check application logs/traces for root cause

### Task: Capacity Planning

1. **Global Infrastructure**: Track ingestion rate growth
2. **Monitoring Stack Health**: Check vmstorage disk usage trend
3. **Application Performance**: Identify traffic patterns by time of day
4. Use data to project future capacity needs

### Task: Performance Optimization

1. **Application Performance**: Identify slowest endpoints
2. **Monitoring Stack Health**: Rule out infrastructure issues
3. Focus optimization efforts on slow endpoints
4. After fixes: Compare before/after latency in graphs

## Advanced Features

### Dashboard Variables (Templating)

Variables allow dynamic filtering:
- `$env` in Application Performance dashboard
- `$cluster` in Monitoring Stack Health

**Creating new variables**:
1. Dashboard settings → Variables → Add variable
2. Type: Query
3. Query: `label_values(metric_name, label_name)`
4. Use in panels: `{label="$variable"}`

### Annotations

Add events to dashboards:
1. Dashboard settings → Annotations
2. Create annotation
3. Example: Mark deployments, incidents
4. Annotations show as vertical lines on graphs

### Dashboard Links

Navigate between related dashboards:
1. Dashboard settings → Links
2. Add link to related dashboard
3. Links appear at top of dashboard

## Troubleshooting

### Dashboard Shows "No Data"

**Check**:
1. Time range: Is it too far in past?
2. Variables: Are filters too restrictive?
3. VictoriaMetrics datasource: Settings → Test
4. Query directly in Explore

### Dashboard Loads Slowly

**Causes**:
1. Too many panels (> 20)
2. Complex queries with many series
3. Long time range (> 7 days)

**Solutions**:
1. Reduce panel count
2. Optimize queries (more specific labels)
3. Use shorter time ranges
4. Enable query caching in VictoriaMetrics

### Variables Not Populating

**Check**:
1. Datasource selected correctly
2. Query syntax correct
3. Metrics exist with that label
4. Try in Explore first to test query

## Best Practices

1. **Start Broad, Then Narrow**: Use Global overview → drill down to specific cluster
2. **Use Variables**: Don't create separate dashboards per cluster
3. **Set Appropriate Time Ranges**: 1h for real-time, 24h for trends, 7d for weekly review
4. **Enable Alerts**: Don't just look at dashboards, set up proactive alerts
5. **Regular Reviews**: Weekly review of all 4 dashboards to catch slow-developing issues
6. **Document Baselines**: Note normal values for each panel during healthy state

## Next Steps

- [Latency Monitoring Guide](latency-monitoring.md) - Deep dive into latency metrics
- [Network Latency Simulation](network-latency-simulation.md) - Test under various latency conditions
- [Quick Start Guide](quick-start.md) - Get started with the stack

