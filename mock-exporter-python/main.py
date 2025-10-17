#!/usr/bin/env python3
"""
Mock Metrics Exporter for Prometheus Remote Write Demo

Generates production-like metrics following Prometheus naming conventions:
- HTTP Service Metrics (RED method: Rate, Errors, Duration)
- Node/System Metrics (USE method: Utilization, Saturation, Errors)
- Application Business Metrics

Supports both counter and gauge metrics with realistic value simulation.
"""

import asyncio
import logging
import os
import random
import signal
import sys
import time
from typing import Dict, List, Any, Optional

import yaml
from fastapi import FastAPI
from prometheus_client import (
    Counter,
    Gauge,
    Histogram,
    Info,
    generate_latest,
    CONTENT_TYPE_LATEST,
    REGISTRY,
)
import uvicorn

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Global metrics storage
metrics_registry: Dict[str, Any] = {}


class MockExporter:
    """Mock metrics exporter that generates realistic production-like metrics."""

    def __init__(self, config_path: str = "config.yml"):
        self.config_path = config_path
        self.config = self._load_config()
        self.running = True
        self.tasks: List[asyncio.Task] = []

    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from YAML file."""
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)
            logger.info(f"Loaded config from {self.config_path}")
            return config
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            sys.exit(1)

    def _random_delta(self, base_value: float, variation: float = 0.1) -> float:
        """Generate random delta around base value."""
        return base_value * (1 + random.uniform(-variation, variation))

    def _create_histogram(self, name: str, labels: Dict[str, str], buckets: List[float]) -> Histogram:
        """Create histogram metric with custom buckets."""
        return Histogram(
            name,
            f"Histogram for {name}",
            labelnames=list(labels.keys()),
            buckets=buckets,
        )

    def _create_counter(self, name: str, labels: Dict[str, str]) -> Counter:
        """Create counter metric."""
        return Counter(
            name,
            f"Counter for {name}",
            labelnames=list(labels.keys()),
        )

    def _create_gauge(self, name: str, labels: Dict[str, str]) -> Gauge:
        """Create gauge metric."""
        return Gauge(
            name,
            f"Gauge for {name}",
            labelnames=list(labels.keys()),
        )

    def _create_info(self, name: str, labels: Dict[str, str]) -> Info:
        """Create info metric."""
        return Info(
            name,
            f"Info for {name}",
        )

    def _register_label_metrics(self):
        """Register info-style metrics from label_metrics config."""
        for i, label_set in enumerate(self.config.get("label_metrics", [])):
            info_metric = self._create_info(f"mock_tag_info_{i}", label_set)
            info_metric.info(label_set)

    def _register_http_metrics(self):
        """Register HTTP service metrics (RED method)."""
        # Group metrics by name and type to avoid duplicates
        metric_groups = {}
        
        for metric_config in self.config.get("http_metrics", []):
            name = metric_config["name"]
            metric_type = metric_config["type"]
            group_key = f"{name}_{metric_type}"
            
            if group_key not in metric_groups:
                metric_groups[group_key] = []
            metric_groups[group_key].append(metric_config)
        
        # Create metrics for each group
        for group_key, configs in metric_groups.items():
            # Use first config to create the metric
            first_config = configs[0]
            name = first_config["name"]
            metric_type = first_config["type"]
            
            if metric_type == "histogram":
                # Get all unique label names from all configs
                all_label_names = set()
                for config in configs:
                    all_label_names.update(config["labels"].keys())
                
                buckets = first_config.get("buckets", [0.1, 0.5, 1, 2.5, 5, 10])
                metric = Histogram(
                    name,
                    f"Histogram for {name}",
                    labelnames=list(all_label_names),
                    buckets=buckets,
                )
            elif metric_type == "counter":
                # Get all unique label names from all configs
                all_label_names = set()
                for config in configs:
                    all_label_names.update(config["labels"].keys())
                
                metric = Counter(
                    name,
                    f"Counter for {name}",
                    labelnames=list(all_label_names),
                )
            else:
                continue
            
            # Store all configs for this metric
            metrics_registry[group_key] = {
                "metric": metric,
                "type": metric_type,
                "configs": configs,
            }

    def _register_node_metrics(self):
        """Register node/system metrics (USE method)."""
        # Group metrics by name and type to avoid duplicates
        metric_groups = {}
        
        for metric_config in self.config.get("node_metrics", []):
            name = metric_config["name"]
            metric_type = metric_config["type"]
            group_key = f"{name}_{metric_type}"
            
            if group_key not in metric_groups:
                metric_groups[group_key] = []
            metric_groups[group_key].append(metric_config)
        
        # Create metrics for each group
        for group_key, configs in metric_groups.items():
            # Use first config to create the metric
            first_config = configs[0]
            name = first_config["name"]
            metric_type = first_config["type"]
            
            if metric_type == "histogram":
                # Get all unique label names from all configs
                all_label_names = set()
                for config in configs:
                    all_label_names.update(config["labels"].keys())
                
                buckets = first_config.get("buckets", [0.1, 0.5, 1, 2.5, 5, 10])
                metric = Histogram(
                    name,
                    f"Histogram for {name}",
                    labelnames=list(all_label_names),
                    buckets=buckets,
                )
            elif metric_type == "counter":
                # Get all unique label names from all configs
                all_label_names = set()
                for config in configs:
                    all_label_names.update(config["labels"].keys())
                
                metric = Counter(
                    name,
                    f"Counter for {name}",
                    labelnames=list(all_label_names),
                )
            elif metric_type == "gauge":
                # Get all unique label names from all configs
                all_label_names = set()
                for config in configs:
                    all_label_names.update(config["labels"].keys())
                
                metric = Gauge(
                    name,
                    f"Gauge for {name}",
                    labelnames=list(all_label_names),
                )
            else:
                continue
            
            # Store all configs for this metric
            metrics_registry[group_key] = {
                "metric": metric,
                "type": metric_type,
                "configs": configs,
            }

    def _register_app_metrics(self):
        """Register application business metrics."""
        # Group metrics by name and type to avoid duplicates
        metric_groups = {}
        
        for metric_config in self.config.get("app_metrics", []):
            name = metric_config["name"]
            metric_type = metric_config["type"]
            group_key = f"{name}_{metric_type}"
            
            if group_key not in metric_groups:
                metric_groups[group_key] = []
            metric_groups[group_key].append(metric_config)
        
        # Create metrics for each group
        for group_key, configs in metric_groups.items():
            # Use first config to create the metric
            first_config = configs[0]
            name = first_config["name"]
            metric_type = first_config["type"]
            
            if metric_type == "histogram":
                # Get all unique label names from all configs
                all_label_names = set()
                for config in configs:
                    all_label_names.update(config["labels"].keys())
                
                buckets = first_config.get("buckets", [0.1, 0.5, 1, 2.5, 5, 10])
                metric = Histogram(
                    name,
                    f"Histogram for {name}",
                    labelnames=list(all_label_names),
                    buckets=buckets,
                )
            elif metric_type == "counter":
                # Get all unique label names from all configs
                all_label_names = set()
                for config in configs:
                    all_label_names.update(config["labels"].keys())
                
                metric = Counter(
                    name,
                    f"Counter for {name}",
                    labelnames=list(all_label_names),
                )
            elif metric_type == "gauge":
                # Get all unique label names from all configs
                all_label_names = set()
                for config in configs:
                    all_label_names.update(config["labels"].keys())
                
                metric = Gauge(
                    name,
                    f"Gauge for {name}",
                    labelnames=list(all_label_names),
                )
            else:
                continue
            
            # Store all configs for this metric
            metrics_registry[group_key] = {
                "metric": metric,
                "type": metric_type,
                "configs": configs,
            }

    def _register_probe_metrics(self):
        """Register cross-region probe metrics."""
        metric_groups = {}
        for metric_config in self.config.get("probe_metrics", []):
            name = metric_config["name"]
            metric_type = metric_config["type"]
            group_key = f"{name}_{metric_type}"
            if group_key not in metric_groups:
                metric_groups[group_key] = []
            metric_groups[group_key].append(metric_config)
        
        for group_key, configs in metric_groups.items():
            first_config = configs[0]
            name = first_config["name"]
            metric_type = first_config["type"]
            
            all_label_names = set()
            for config in configs:
                all_label_names.update(config["labels"].keys())
            
            if metric_type == "histogram":
                buckets = first_config.get("buckets", [0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0])
                metric = Histogram(
                    name,
                    f"Histogram for {name}",
                    labelnames=list(all_label_names),
                    buckets=buckets,
                )
            elif metric_type == "counter":
                metric = Counter(
                    name,
                    f"Counter for {name}",
                    labelnames=list(all_label_names),
                )
            elif metric_type == "gauge":
                metric = Gauge(
                    name,
                    f"Gauge for {name}",
                    labelnames=list(all_label_names),
                )
            else:
                continue
            
            # Store all configs for this metric
            metrics_registry[group_key] = {
                "metric": metric,
                "type": metric_type,
                "configs": configs,
            }

    def _register_slo_metrics(self):
        """Register SLO/SLI metrics."""
        metric_groups = {}
        for metric_config in self.config.get("slo_metrics", []):
            name = metric_config["name"]
            metric_type = metric_config["type"]
            group_key = f"{name}_{metric_type}"
            if group_key not in metric_groups:
                metric_groups[group_key] = []
            metric_groups[group_key].append(metric_config)
        
        for group_key, configs in metric_groups.items():
            first_config = configs[0]
            name = first_config["name"]
            metric_type = first_config["type"]
            
            all_label_names = set()
            for config in configs:
                all_label_names.update(config["labels"].keys())
            
            if metric_type == "gauge":
                metric = Gauge(
                    name,
                    f"Gauge for {name}",
                    labelnames=list(all_label_names),
                )
            elif metric_type == "counter":
                metric = Counter(
                    name,
                    f"Counter for {name}",
                    labelnames=list(all_label_names),
                )
            else:
                continue
            
            # Store all configs for this metric
            metrics_registry[group_key] = {
                "metric": metric,
                "type": metric_type,
                "configs": configs,
            }

    async def _update_histogram_metric(self, metric_info: Dict[str, Any]):
        """Update histogram metric with realistic values."""
        metric = metric_info["metric"]
        configs = metric_info["configs"]

        while self.running:
            # Update each config
            for config in configs:
                base_value = config["value"]
                labels = config["labels"]
                
                # Generate realistic value with some variation
                value = self._random_delta(base_value, 0.2)
                
                # For histograms, we observe the value
                metric.labels(**labels).observe(value)
            
            await asyncio.sleep(random.uniform(2, 5))

    async def _update_counter_metric(self, metric_info: Dict[str, Any]):
        """Update counter metric with realistic increments."""
        metric = metric_info["metric"]
        configs = metric_info["configs"]

        while self.running:
            # Update each config
            for config in configs:
                base_value = config["value"]
                labels = config["labels"]
                
                # Generate realistic increment
                increment = self._random_delta(base_value * 0.1, 0.5)
                metric.labels(**labels).inc(increment)
            
            await asyncio.sleep(random.uniform(1, 3))

    async def _update_gauge_metric(self, metric_info: Dict[str, Any]):
        """Update gauge metric with realistic values."""
        metric = metric_info["metric"]
        configs = metric_info["configs"]

        # Initialize current values for each config
        current_values = {}
        for config in configs:
            current_values[hash(str(sorted(config["labels"].items())))] = config["value"]

        while self.running:
            # Update each config
            for config in configs:
                base_value = config["value"]
                labels = config["labels"]
                config_key = hash(str(sorted(labels.items())))
                
                # Generate realistic value with some drift
                delta = self._random_delta(base_value * 0.05, 0.3)
                current_values[config_key] += delta
                
                # Keep values within reasonable bounds
                if "memory" in metric._name or "disk" in metric._name:
                    current_values[config_key] = max(0, min(current_values[config_key], base_value * 1.5))
                elif "cpu" in metric._name:
                    current_values[config_key] = max(0, min(current_values[config_key], 100))
                
                metric.labels(**labels).set(current_values[config_key])
            
            await asyncio.sleep(random.uniform(2, 4))

    async def _start_metric_updaters(self):
        """Start background tasks to update metrics."""
        for metric_info in metrics_registry.values():
            if metric_info["type"] == "histogram":
                task = asyncio.create_task(self._update_histogram_metric(metric_info))
            elif metric_info["type"] == "counter":
                task = asyncio.create_task(self._update_counter_metric(metric_info))
            elif metric_info["type"] == "gauge":
                task = asyncio.create_task(self._update_gauge_metric(metric_info))
            else:
                continue
            
            self.tasks.append(task)

    def register_metrics(self):
        """Register all metrics from configuration."""
        logger.info("Registering metrics...")
        self._register_label_metrics()
        self._register_http_metrics()
        self._register_node_metrics()
        self._register_app_metrics()
        self._register_probe_metrics()
        self._register_slo_metrics()
        logger.info(f"Registered {len(metrics_registry)} metrics")

    async def start(self):
        """Start the metrics exporter."""
        logger.info("Starting mock metrics exporter...")
        self.register_metrics()
        await self._start_metric_updaters()
        logger.info("Mock metrics exporter started successfully")

    async def stop(self):
        """Stop the metrics exporter."""
        logger.info("Stopping mock metrics exporter...")
        self.running = False
        
        # Cancel all running tasks
        for task in self.tasks:
            task.cancel()
        
        # Wait for tasks to complete
        await asyncio.gather(*self.tasks, return_exceptions=True)
        logger.info("Mock metrics exporter stopped")

    def get_metrics_count(self) -> int:
        """Get the number of registered metrics."""
        return len(metrics_registry)


# FastAPI app for serving metrics
app = FastAPI(title="Mock Metrics Exporter", version="0.1.0")
exporter: Optional[MockExporter] = None


@app.on_event("startup")
async def startup_event():
    """Initialize the exporter on startup."""
    global exporter
    exporter = MockExporter()
    await exporter.start()


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    global exporter
    if exporter:
        await exporter.stop()


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    from fastapi.responses import Response
    return Response(content=generate_latest(REGISTRY), media_type="text/plain; version=0.0.4; charset=utf-8")


@app.get("/healthz")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "metrics_count": exporter.get_metrics_count() if exporter else 0}


@app.get("/")
async def root():
    """Root endpoint with basic info."""
    return {
        "service": "mock-metrics-exporter",
        "version": "0.1.0",
        "endpoints": {
            "metrics": "/metrics",
            "health": "/healthz",
        },
        "metrics_count": exporter.get_metrics_count() if exporter else 0,
    }


def signal_handler(signum, frame):
    """Handle shutdown signals."""
    logger.info(f"Received signal {signum}, shutting down...")
    sys.exit(0)


def main():
    """Main entry point."""
    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Get configuration from environment
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "2112"))
    log_level = os.getenv("LOG_LEVEL", "info")
    
    logger.info(f"Starting server on {host}:{port}")
    
    # Run the server
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        log_level=log_level,
        access_log=True,
    )


if __name__ == "__main__":
    main()
