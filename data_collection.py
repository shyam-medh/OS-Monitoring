import psutil
import time
import subprocess
from threading import Thread, Lock

class ProcessDataCollector:
    """
    Optimized process data collector with non-blocking updates and smart caching.
    """
    def __init__(self):
        self.last_cpu_update = 0
        self.last_full_update = 0
        self.cpu_data_cache = {}
        self.name_cache = {}
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
                    with proc.oneshot():
                        # Use defaults for missing attributes (fixes AccessDenied issues)
                        pid = proc.pid
                        info = proc.info
                        
                        # Robust name retrieval
                        name = info.get('name')
                        if not name:
                            try:
                                name = proc.name()
                            except (psutil.AccessDenied, psutil.ZombieProcess):
                                name = "Access Denied" if psutil.pid_exists(pid) else "Terminated"
                            except Exception:
                                name = "Unknown"
                        
                        if not name or name == "Unknown":
                            # Attempt expensive fallback (cached) for persistent system processes
                            if pid in self.name_cache:
                                name = self.name_cache[pid]
                            else:
                                try:
                                    # Fallback to tasklist for stubborn Windows processes (e.g. Secure System)
                                    # Use a list for command arguments to handle spaces correctly and safely
                                    cmd = ['tasklist', '/FI', f'PID eq {pid}', '/NH', '/FO', 'CSV']
                                    # usage of creationflags=0x08000000 (CREATE_NO_WINDOW) prevents console window flash
                                    output = subprocess.check_output(cmd, creationflags=0x08000000).decode(errors='ignore')
                                    if output.strip():
                                        parts = output.split('","')
                                        if len(parts) > 0:
                                            found = parts[0].strip('"')
                                            self.name_cache[pid] = found
                                            name = found
                                except Exception:
                                    self.name_cache[pid] = "Unknown"
                        
                        if not name:
                            name = "Unknown"
                        
                        # Robust state retrieval
                        state = info.get('status')
                        if not state:
                            try:
                                state = proc.status()
                            except Exception:
                                state = "unknown"

                        # Robust memory retrieval (don't skip if denied)
                        mem_info = info.get('memory_info')
                        memory_mb = 0.0
                        if mem_info:
                            memory_mb = mem_info.rss / (1024 * 1024)
                        
                        # Robust start time
                        create_time = info.get('create_time', 0)
                            
                        process_info = {
                            'pid': pid,
                            'name': name,
                            'state': state,
                            'cpu_percent': 0.0,
                            'memory_mb': memory_mb,
                            'start_time': create_time
                        }
                        
                        if update_cpu:
                            try:
                                process_info['cpu_percent'] = proc.cpu_percent(interval=None) or 0.0
                                self.cpu_data_cache[pid] = process_info['cpu_percent']
                            except Exception:
                                process_info['cpu_percent'] = self.cpu_data_cache.get(pid, 0.0)
                        else:
                            process_info['cpu_percent'] = self.cpu_data_cache.get(pid, 0.0)
                        
                        processes.append(process_info)
                        
                except (psutil.NoSuchProcess, psutil.ZombieProcess):
                    continue
                except Exception:
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
                
                # Clean up name cache periodically
                if len(self.name_cache) > 200:
                    active_pids = {p['pid'] for p in processes}
                    self.name_cache = {k: v for k, v in self.name_cache.items() if k in active_pids}
                    
        finally:
            self.is_collecting = False