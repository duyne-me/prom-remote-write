# Network Latency Simulation Guide

Hướng dẫn chi tiết về cách simulate network latency cho Multi-Region monitoring setup sử dụng `tc` (Traffic Control).

## Tổng quan

Trong môi trường production thực tế, các region khác nhau có độ trễ mạng khác nhau dựa trên khoảng cách địa lý. Việc simulate network latency giúp:

- Test hệ thống monitoring trong điều kiện thực tế
- Hiểu được tác động của độ trễ đến remote write performance
- Validate dashboard và alerts hoạt động đúng với các giá trị latency khác nhau
- Tối ưu hóa cấu hình cho multi-region deployment

## Prerequisites

### Yêu cầu hệ thống

- Linux host (hoặc WSL2 trên Windows)
- Docker đã cài đặt và containers đang chạy
- Quyền root hoặc sudo access
- Package `iproute2` (chứa `tc` command)

### Cài đặt iproute2

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install iproute2
```

**RHEL/CentOS:**
```bash
sudo yum install iproute
```

**macOS:**
```bash
# tc không có sẵn trên macOS, cần dùng Linux VM hoặc Docker
```

## Sử dụng Script

Script `scripts/simulate-latency.sh` cung cấp interface đơn giản để thêm/xóa network latency.

### Thêm Network Latency

**Cú pháp:**
```bash
./scripts/simulate-latency.sh add <container_name> <delay_ms> [jitter_ms]
```

**Ví dụ:**
```bash
# Thêm 100ms delay với 20ms jitter cho vmagent-eu-west-1
./scripts/simulate-latency.sh add vmagent-eu-west-1 100 20

# Thêm 50ms delay không có jitter
./scripts/simulate-latency.sh add vmagent-ap-southeast-1 50
```

### Xóa Network Latency

**Cú pháp:**
```bash
./scripts/simulate-latency.sh remove <container_name>
```

**Ví dụ:**
```bash
./scripts/simulate-latency.sh remove vmagent-eu-west-1
```

### Liệt kê Latency Settings

**Cú pháp:**
```bash
./scripts/simulate-latency.sh list
```

**Output:**
```
[INFO] Checking network latency for all vmagent containers...
  vmagent-us-east-1: No latency configured
  vmagent-eu-west-1: delay 100.0ms
  vmagent-ap-southeast-1: delay 50.0ms
  vmagent-sa-east-1: Not running
```

## Scenarios Testing

### 1. Baseline (No Latency)

Không có network delay - dùng để so sánh baseline performance.

```bash
# Đảm bảo không có latency được apply
./scripts/simulate-latency.sh list
```

### 2. Low Latency (10-50ms)

Simulate cùng datacenter hoặc cùng region.

```bash
# Same datacenter - 10ms
./scripts/simulate-latency.sh add vmagent-us-east-1 10

# Same region - 30ms
./scripts/simulate-latency.sh add vmagent-eu-west-1 30 5
```

**Expected Impact:**
- Remote write latency tăng nhẹ (~10-50ms)
- Pending bytes có thể tăng nhẹ nhưng vẫn trong ngưỡng an toàn
- Success rate vẫn gần 100%

### 3. Medium Latency (50-100ms)

Simulate cross-region trong cùng continent (ví dụ: US East → US West).

```bash
# Cross-region - 75ms với 10ms jitter
./scripts/simulate-latency.sh add vmagent-ap-southeast-1 75 10
```

**Expected Impact:**
- Remote write latency tăng đáng kể (~50-100ms)
- Pending bytes có thể tăng nhưng vẫn manageable
- Success rate vẫn cao (>99%)

### 4. High Latency (150-300ms)

Simulate cross-continent (ví dụ: US → Europe, US → Asia).

```bash
# Cross-continent - 200ms với 30ms jitter
./scripts/simulate-latency.sh add vmagent-eu-west-1 200 30

# Very high latency - 300ms
./scripts/simulate-latency.sh add vmagent-sa-east-1 300 50
```

**Expected Impact:**
- Remote write latency tăng đáng kể (~150-300ms)
- Pending bytes có thể tăng cao, cần monitor chặt chẽ
- Success rate có thể giảm nhẹ nếu timeout không đủ
- Có thể cần tăng `remote_timeout` trong config

### 5. Very High Latency (300ms+)

Simulate extreme cases (ví dụ: satellite link, poor network conditions).

```bash
# Extreme latency - 500ms với 100ms jitter
./scripts/simulate-latency.sh add vmagent-sa-east-1 500 100
```

**Expected Impact:**
- Remote write latency rất cao
- Pending bytes có thể tăng rất cao, risk of data loss
- Success rate có thể giảm đáng kể
- Cần điều chỉnh cấu hình (timeout, batch size, etc.)

## Monitoring Latency Impact

Sau khi apply latency, monitor các metrics sau trên Grafana Latency Dashboard:

### 1. Remote Write Latency

**Query:**
```promql
histogram_quantile(0.95, sum(rate(vmagent_remotewrite_send_duration_seconds_bucket[5m])) by (le, region))
```

**Expected:**
- Latency tăng tương ứng với delay được apply
- Ví dụ: Apply 100ms delay → remote write latency tăng ~100ms

### 2. Pending Bytes

**Query:**
```promql
vmagent_remotewrite_pending_bytes
```

**Expected:**
- Pending bytes tăng khi latency cao
- Alert nếu > 10MB
- Nếu pending bytes tăng liên tục → có thể cần tăng timeout hoặc giảm scrape interval

### 3. Success Rate

**Query:**
```promql
sum(rate(vmagent_remotewrite_send_duration_seconds_count{status="ok"}[5m])) by (region) / 
sum(rate(vmagent_remotewrite_send_duration_seconds_count[5m])) by (region) * 100
```

**Expected:**
- Vẫn > 99% với latency < 300ms
- Có thể giảm với latency > 300ms nếu timeout không đủ

## Manual tc Commands

Nếu muốn dùng `tc` trực tiếp thay vì script:

### Thêm Latency

```bash
# Lấy container PID
CONTAINER_NAME="vmagent-eu-west-1"
PID=$(docker inspect -f '{{.State.Pid}}' $CONTAINER_NAME)

# Thêm 100ms delay với 20ms jitter
sudo nsenter -n -t $PID tc qdisc add dev eth0 root netem delay 100ms 20ms
```

### Xóa Latency

```bash
sudo nsenter -n -t $PID tc qdisc del dev eth0 root
```

### Kiểm tra Current Settings

```bash
sudo nsenter -n -t $PID tc qdisc show dev eth0
```

### Thêm Packet Loss (Optional)

```bash
# 100ms delay + 1% packet loss
sudo nsenter -n -t $PID tc qdisc add dev eth0 root netem delay 100ms loss 1%
```

## Troubleshooting

### Container không tìm thấy

**Error:** `Container 'vmagent-eu-west-1' not found or not running`

**Solution:**
```bash
# Kiểm tra containers đang chạy
docker ps

# Đảm bảo container name đúng
docker ps --format '{{.Names}}'
```

### Permission Denied

**Error:** `Permission denied` khi chạy tc

**Solution:**
```bash
# Sử dụng sudo
sudo ./scripts/simulate-latency.sh add vmagent-eu-west-1 100 20
```

### tc Command Not Found

**Error:** `tc: command not found`

**Solution:**
```bash
# Cài đặt iproute2
sudo apt-get install iproute2  # Ubuntu/Debian
sudo yum install iproute        # RHEL/CentOS
```

### Latency không có hiệu lực

**Possible Causes:**
1. Container đã restart → latency settings bị mất
2. Network interface không phải `eth0` → kiểm tra với `ip addr` trong container
3. tc rules bị xóa bởi container restart

**Solution:**
```bash
# Kiểm tra network interface trong container
docker exec vmagent-eu-west-1 ip addr

# Re-apply latency sau khi container restart
./scripts/simulate-latency.sh add vmagent-eu-west-1 100 20
```

## Best Practices

1. **Test Incrementally**: Bắt đầu với latency thấp, tăng dần để quan sát impact
2. **Monitor Dashboard**: Luôn mở Grafana Latency Dashboard khi test
3. **Baseline First**: Test baseline (no latency) trước để có reference point
4. **Clean Up**: Xóa latency sau khi test xong để tránh confusion
5. **Document Results**: Ghi lại kết quả test để reference sau này

## Real-World Latency Values

Tham khảo latency thực tế giữa các AWS regions:

| From Region | To Region | Typical Latency |
|-------------|-----------|-----------------|
| us-east-1 | us-west-1 | 60-80ms |
| us-east-1 | eu-west-1 | 70-90ms |
| us-east-1 | ap-southeast-1 | 180-220ms |
| eu-west-1 | ap-southeast-1 | 200-250ms |
| us-east-1 | sa-east-1 | 150-180ms |

## References

- [Linux Traffic Control (tc) Documentation](https://man7.org/linux/man-pages/man8/tc.8.html)
- [Network Emulation with netem](https://wiki.linuxfoundation.org/networking/netem)
- [Docker Network Namespaces](https://docs.docker.com/network/)

