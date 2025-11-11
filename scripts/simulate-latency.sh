#!/bin/bash

# Network Latency Simulation Script
# Uses tc (Traffic Control) to add/remove network delay and jitter to Docker containers
#
# Usage:
#   ./simulate-latency.sh add <container_name> <delay_ms> [jitter_ms]
#   ./simulate-latency.sh remove <container_name>
#   ./simulate-latency.sh list
#
# Examples:
#   ./simulate-latency.sh add vmagent-eu-west-1 100 20
#   ./simulate-latency.sh remove vmagent-eu-west-1
#   ./simulate-latency.sh list

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Function to get container PID
get_container_pid() {
    local container_name=$1
    local pid=$(docker inspect -f '{{.State.Pid}}' "$container_name" 2>/dev/null)
    
    if [ -z "$pid" ] || [ "$pid" = "0" ]; then
        print_error "Container '$container_name' not found or not running"
        return 1
    fi
    
    echo "$pid"
}

# Function to get container network namespace
get_container_netns() {
    local container_name=$1
    local pid=$(get_container_pid "$container_name")
    
    if [ $? -ne 0 ]; then
        return 1
    fi
    
    echo "/proc/$pid/ns/net"
}

# Function to add network delay
add_latency() {
    local container_name=$1
    local delay_ms=$2
    local jitter_ms=${3:-0}
    
    print_info "Adding ${delay_ms}ms delay${jitter_ms:+, ${jitter_ms}ms jitter} to container '$container_name'"
    
    # Check if container exists
    if ! docker ps --format '{{.Names}}' | grep -q "^${container_name}$"; then
        print_error "Container '$container_name' is not running"
        return 1
    fi
    
    local pid=$(get_container_pid "$container_name")
    if [ $? -ne 0 ]; then
        return 1
    fi
    
    # Check if tc is available
    if ! command -v tc &> /dev/null; then
        print_error "tc (Traffic Control) command not found. Please install iproute2 package."
        print_info "On Ubuntu/Debian: sudo apt-get install iproute2"
        print_info "On RHEL/CentOS: sudo yum install iproute"
        return 1
    fi
    
    # Check if we have root/sudo access
    if [ "$EUID" -ne 0 ]; then
        print_warning "This script requires root privileges. Using sudo..."
        SUDO_CMD="sudo"
    else
        SUDO_CMD=""
    fi
    
    # Enter container network namespace and add delay
    local netns="/proc/$pid/ns/net"
    
    # Remove existing qdisc if any
    $SUDO_CMD nsenter -n -t "$pid" tc qdisc del dev eth0 root 2>/dev/null || true
    
    # Add new qdisc with delay
    if [ "$jitter_ms" -gt 0 ]; then
        $SUDO_CMD nsenter -n -t "$pid" tc qdisc add dev eth0 root netem delay ${delay_ms}ms ${jitter_ms}ms
        print_info "Added ${delay_ms}ms delay with ${jitter_ms}ms jitter"
    else
        $SUDO_CMD nsenter -n -t "$pid" tc qdisc add dev eth0 root netem delay ${delay_ms}ms
        print_info "Added ${delay_ms}ms delay"
    fi
    
    print_info "Network latency simulation applied successfully"
    print_info "To verify: docker exec $container_name ping -c 3 <target_host>"
}

# Function to remove network delay
remove_latency() {
    local container_name=$1
    
    print_info "Removing network latency from container '$container_name'"
    
    local pid=$(get_container_pid "$container_name")
    if [ $? -ne 0 ]; then
        return 1
    fi
    
    # Check if we have root/sudo access
    if [ "$EUID" -ne 0 ]; then
        SUDO_CMD="sudo"
    else
        SUDO_CMD=""
    fi
    
    # Remove qdisc
    if $SUDO_CMD nsenter -n -t "$pid" tc qdisc del dev eth0 root 2>/dev/null; then
        print_info "Network latency removed successfully"
    else
        print_warning "No network latency rules found or already removed"
    fi
}

# Function to list current latency settings
list_latency() {
    print_info "Checking network latency for all vmagent containers..."
    
    local containers=("vmagent-us-east-1" "vmagent-eu-west-1" "vmagent-ap-southeast-1" "vmagent-sa-east-1")
    
    if [ "$EUID" -ne 0 ]; then
        SUDO_CMD="sudo"
    else
        SUDO_CMD=""
    fi
    
    for container in "${containers[@]}"; do
        if docker ps --format '{{.Names}}' | grep -q "^${container}$"; then
            local pid=$(get_container_pid "$container" 2>/dev/null)
            if [ $? -eq 0 ]; then
                local delay_info=$($SUDO_CMD nsenter -n -t "$pid" tc qdisc show dev eth0 2>/dev/null | grep -o "delay [0-9.]*ms" || echo "none")
                if [ "$delay_info" = "none" ]; then
                    echo "  $container: No latency configured"
                else
                    echo "  $container: $delay_info"
                fi
            fi
        else
            echo "  $container: Not running"
        fi
    done
}

# Function to show usage
show_usage() {
    cat << EOF
Network Latency Simulation Script

Usage:
    $0 <command> [options]

Commands:
    add <container_name> <delay_ms> [jitter_ms]
        Add network delay to a container
        - container_name: Name of the Docker container
        - delay_ms: Delay in milliseconds
        - jitter_ms: Optional jitter in milliseconds (default: 0)

    remove <container_name>
        Remove network delay from a container

    list
        List current latency settings for all vmagent containers

Examples:
    # Add 100ms delay with 20ms jitter to vmagent-eu-west-1
    $0 add vmagent-eu-west-1 100 20

    # Add 50ms delay without jitter
    $0 add vmagent-ap-southeast-1 50

    # Remove latency from vmagent-eu-west-1
    $0 remove vmagent-eu-west-1

    # List all latency settings
    $0 list

Scenarios:
    Low Latency:    10-50ms   (same datacenter)
    Medium Latency: 50-100ms  (same region)
    High Latency:   150-300ms (cross-region)
    Very High:      300ms+    (cross-continent)

Note: This script requires root privileges or sudo access.
EOF
}

# Main script logic
main() {
    case "${1:-}" in
        add)
            if [ $# -lt 3 ]; then
                print_error "Missing arguments for 'add' command"
                show_usage
                exit 1
            fi
            add_latency "$2" "$3" "${4:-0}"
            ;;
        remove)
            if [ $# -lt 2 ]; then
                print_error "Missing container name for 'remove' command"
                show_usage
                exit 1
            fi
            remove_latency "$2"
            ;;
        list)
            list_latency
            ;;
        help|--help|-h)
            show_usage
            ;;
        *)
            print_error "Unknown command: ${1:-}"
            show_usage
            exit 1
            ;;
    esac
}

# Run main function
main "$@"

