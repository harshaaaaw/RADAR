"""
Resource Monitor - System resource monitoring
"""

import psutil
from typing import Dict, Any

from core.logging_manager import get_logger
from core.config_manager import get_config

logger = get_logger("orchestrator.resources")


class ResourceMonitor:
    """Monitors system resources (CPU, RAM, Disk)"""
    
    def __init__(self):
        self.config = get_config()
        self.thresholds = self.config.orchestrator
    
    def check_resources(self) -> Dict[str, Any]:
        """Check current resource usage"""
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage(self.config.paths.working_root)
        
        # Check thresholds
        cpu_high = cpu_percent > self.thresholds.cpu['high_threshold_percent']
        
        memory_gb = memory.used / (1024**3)
        memory_warning = memory_gb > self.thresholds.memory['warning_threshold_gb']
        memory_critical = memory_gb > self.thresholds.memory['critical_threshold_gb']
        
        disk_gb_free = disk.free / (1024**3)
        disk_warning = disk_gb_free < self.thresholds.disk['warning_threshold_gb']
        disk_critical = disk_gb_free < self.thresholds.disk['critical_threshold_gb']
        
        result = {
            'cpu_percent': cpu_percent,
            'cpu_high': cpu_high,
            'memory_used_gb': memory_gb,
            'memory_total_gb': memory.total / (1024**3),
            'memory_percent': memory.percent,
            'memory_warning': memory_warning,
            'memory_critical': memory_critical,
            'disk_used_gb': disk.used / (1024**3),
            'disk_free_gb': disk_gb_free,
            'disk_total_gb': disk.total / (1024**3),
            'disk_percent': disk.percent,
            'disk_warning': disk_warning,
            'disk_critical': disk_critical,
            'critical': memory_critical or disk_critical
        }
        
        # Log warnings
        if cpu_high:
            logger.warning(f"High CPU usage: {cpu_percent:.1f}%")
        
        if memory_warning:
            logger.warning(f"High memory usage: {memory_gb:.1f}GB / {memory.total/(1024**3):.1f}GB ({memory.percent:.1f}%)")
        
        if disk_warning:
            logger.warning(f"Low disk space: {disk_gb_free:.1f}GB free")
        
        return result
