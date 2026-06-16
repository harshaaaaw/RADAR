"""
Health Monitor - Service health checking
"""

import requests
from typing import Dict, Any

from core.logging_manager import get_logger
from core.config_manager import get_config

logger = get_logger("orchestrator.health")


class HealthMonitor:
    """Monitors health of external services"""
    
    def __init__(self):
        self.config = get_config()
    
    def check_all_services(self) -> Dict[str, Any]:
        """Check health of all services"""
        return {
            'tika': self.check_tika(),
            'opensearch': self.check_opensearch(),
            'tesseract': self.check_tesseract()
        }
    
    def check_tika(self) -> Dict[str, bool]:
        """Check Tika instances"""
        results = {}
        
        for instance in self.config.extraction.tika.instances:
            url = f"http://{instance.host}:{instance.port}/tika"
            
            try:
                response = requests.get(url, timeout=5)
                results[instance.port] = response.status_code == 200
            except Exception:
                results[instance.port] = False
        
        return results
    
    def check_opensearch(self) -> bool:
        """Check OpenSearch cluster"""
        try:
            host = self.config.indexing.opensearch.hosts[0]
            response = requests.get(f"{host}/_cluster/health", timeout=5)
            
            if response.status_code == 200:
                health = response.json()
                return health.get('status') in ['green', 'yellow']
        except Exception:
            pass
        
        return False
    
    def check_tesseract(self) -> bool:
        """Check Tesseract availability"""
        import subprocess
        
        try:
            cmd = self.config.ocr.tesseract.command
            result = subprocess.run([cmd, '--version'], capture_output=True, timeout=5)
            return result.returncode == 0
        except Exception:
            return False
