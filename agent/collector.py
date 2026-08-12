"""psutil-based metric collector for EdgeGuard agent."""

import subprocess
from dataclasses import dataclass


@dataclass
class MetricPoint:
    name: str
    value: float
    labels: dict


def collect_metrics() -> list[MetricPoint]:
    """
    Collect host metrics using psutil. Returns a flat list of MetricPoints.
    All metric names match the threshold rule metric_name fields exactly.
    """
    import psutil

    metrics: list[MetricPoint] = []

    # CPU
    cpu_percent = psutil.cpu_percent(interval=1)
    metrics.append(MetricPoint(name="cpu_percent", value=cpu_percent, labels={}))

    # Memory
    mem = psutil.virtual_memory()
    metrics.append(MetricPoint(name="memory_percent", value=mem.percent, labels={}))
    metrics.append(MetricPoint(name="memory_available_bytes", value=mem.available, labels={}))

    # Disk (root partition)
    disk = psutil.disk_usage("/")
    disk_percent = disk.percent
    metrics.append(MetricPoint(name="disk_percent", value=disk_percent, labels={"mount": "/"}))
    metrics.append(MetricPoint(name="disk_free_bytes", value=disk.free, labels={"mount": "/"}))

    # Load average (Linux only)
    try:
        load1, load5, load15 = psutil.getloadavg()
        metrics.append(MetricPoint(name="load_avg_1m", value=load1, labels={}))
        metrics.append(MetricPoint(name="load_avg_5m", value=load5, labels={}))
    except AttributeError:
        pass

    # Network I/O counters
    net = psutil.net_io_counters()
    metrics.append(MetricPoint(name="net_bytes_sent", value=net.bytes_sent, labels={}))
    metrics.append(MetricPoint(name="net_bytes_recv", value=net.bytes_recv, labels={}))

    # Service health — check a configurable list of systemd services
    for service in _get_monitored_services():
        active = _is_service_active(service)
        metrics.append(
            MetricPoint(
                name="service_active",
                value=1.0 if active else 0.0,
                labels={"service_name": service},
            )
        )

    return metrics


def _get_monitored_services() -> list[str]:
    """
    Services to monitor. In production, load from agent config file.
    """
    import os
    services_env = os.environ.get("MONITORED_SERVICES", "sshd,chronyd")
    return [s.strip() for s in services_env.split(",") if s.strip()]


def _is_service_active(service_name: str) -> bool:
    """Check if a systemd service is active. Returns False on any error."""
    try:
        result = subprocess.run(
            ["systemctl", "is-active", service_name],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.stdout.strip() == "active"
    except Exception:
        return False
