"""Module to handle Prometheus metrics."""

from dataclasses import dataclass

from prometheus_client import start_http_server, Enum, Counter

@dataclass
class Metrics:
    """Class to hold prometheus Metrics."""
    lock_target_status = Enum("mqtt_target_lock_status", "Target Lock Status",
                              states=["Locked", "Unlocked"], labelnames=['lock_name'])
    lock_current_status = Enum("mqtt_current_lock_status", "Current Lock Status",
                               states=["Locked", "Unlocked"], labelnames=['lock_name'])
    unlock_counter = Counter('my_failures', 'Description of counter',
                             labelnames=['lock_name'], labelnames=['lock_name', 'key_id'])

@dataclass
class AppMetricsParams:
    """Class to handle prometheus metric export parameters."""
    metrics_enabled = True
    metrics_port = 8000
    lock_name = ""

class AppMetrics:
    """Class to handle prometheus metric export."""
    def __init__(self, params:AppMetricsParams):
        self.params = params
        if self.params.metrics_enabled:
            self.metrics = Metrics()

    @classmethod
    def from_dict(cls, config: dict):
        """Create class from dict."""
        params = AppMetricsParams()
        params.metrics_enabled = config.get("enabled", True)
        params.metrics_port = config.get("metrics_port", 8000)
        params.lock_name = config.get("lock_name", "NFC Lock")
        return AppMetrics(params=params)


    def start_server(self):
        """Start prometheus export server """
        if self.params.metrics_enabled:
            start_http_server(self.params.metrics_port)

    def lock_updated(self, target_locked:bool, current_locked:bool, key_id:str="Homekit"):
        """Export Metric"""
        if self.params.metrics_enabled:
            self.metrics.lock_target_status.labels(
                lock_name=self.params.lock_name).state("Locked" if target_locked else "Unlocked")
            self.metrics.lock_current_status.labels(
                lock_name=self.params.lock_name).state("Locked" if current_locked else "Unlocked")
            self.metrics.unlock_counter.labels(lock_name=self.params.lock_name, key_id=key_id).inc()
