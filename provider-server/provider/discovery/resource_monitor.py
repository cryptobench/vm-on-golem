import psutil

class ResourceMonitor:
    """Monitor system resources."""
    
    @staticmethod
    def get_cpu_count() -> int:
        """Get number of CPU cores."""
        return psutil.cpu_count()

    @staticmethod
    def get_memory_gb() -> int:
        """Get available memory in GB."""
        return psutil.virtual_memory().available // (1024 ** 3)

    @staticmethod
    def get_storage_gb() -> int:
        """Get available storage in GB."""
        return psutil.disk_usage("/").free // (1024 ** 3)

    @staticmethod
    def get_cpu_percent() -> float:
        """Get CPU usage percentage."""
        return psutil.cpu_percent(interval=1)

    @staticmethod
    def get_memory_percent() -> float:
        """Get memory usage percentage."""
        return psutil.virtual_memory().percent

    @staticmethod
    def get_storage_percent() -> float:
        """Get storage usage percentage."""
        return psutil.disk_usage("/").percent