import psutil
import time
from threading import Thread, Lock

class ProcessDataCollector:
    """
    Optimized process data collector with non-blocking updates and smart caching.
    """
    def __init__(self):
        self.last_cpu_update = 0
        self.last_full_update = 0
        self.cpu_data_cache = {}
        self.processes = []
        self.is_collecting = False
        self._lock = Lock()
        self._cached_result = []
        self._cache_timestamp = 0
        self._cache_ttl = 1.5  # Cache valid for 1.5 seconds

    def get_process_data(self):
        """
        Returns process data, using cache if available and fresh.
        Non-blocking: returns cached data if collection in progress.
        """
        current_time = time.time()
        
        # Return cached data if fresh enough (avoids redundant collection)
        if self._cached_result and (current_time - self._cache_timestamp) < self._cache_ttl:
            return self._cached_result
        
        # If already collecting, return last known data (non-blocking!)
        if self.is_collecting:
            return self._cached_result if self._cached_result else self.processes
        
        # Collect synchronously but efficiently
        self._collect_data()
        return self.processes

    def _collect_data(self):
        """Collect process data with optimizations for performance."""
        with self._lock:
            if self.is_collecting:
                return
            self.is_collecting = True
        
        try:
            processes = []
            current_time = time.time()
            
            # Update CPU data every 5 seconds (as before)
            update_cpu = (current_time - self.last_cpu_update) >= 5
            
            # Use oneshot context manager for efficiency (reduces syscalls)
            for proc in psutil.process_iter(['pid', 'name', 'status', 'memory_info', 'create_time']):
                try:
                    with proc.oneshot():  # Batch syscalls for this process
                        pid = proc.info['pid']
                        
                        # Skip processes with no memory info
                        mem_info = proc.info.get('memory_info')
                        if mem_info is None:
                            continue
                            
                        process_info = {
                            'pid': pid,
                            'name': proc.info['name'] or 'Unknown',
                            'state': proc.info['status'] or 'unknown',
                            'cpu_percent': 0.0,
                            'memory_mb': mem_info.rss / (1024 * 1024),
                            'start_time': proc.info['create_time'] or 0
                        }
                        
                        if update_cpu:
                            process_info['cpu_percent'] = proc.cpu_percent(interval=None)
                            self.cpu_data_cache[pid] = process_info['cpu_percent']
                        else:
                            process_info['cpu_percent'] = self.cpu_data_cache.get(pid, 0.0)
                        
                        processes.append(process_info)
                        
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue
                except Exception:
                    # Catch any other psutil errors silently
                    continue

            self.processes = processes
            self._cached_result = processes
            self._cache_timestamp = current_time
            
            if update_cpu:
                self.last_cpu_update = current_time
                # Clean up stale CPU cache entries periodically
                if len(self.cpu_data_cache) > 500:
                    active_pids = {p['pid'] for p in processes}
                    self.cpu_data_cache = {k: v for k, v in self.cpu_data_cache.items() if k in active_pids}
                    
        finally:
            self.is_collecting = False