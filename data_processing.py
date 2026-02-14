import pandas as pd
import psutil
import time

def format_duration(seconds):
    if seconds < 0:
        return "0s"
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    seconds = int(seconds % 60)
    parts = []
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0 or hours > 0:
        parts.append(f"{minutes}m")
    parts.append(f"{seconds}s")
    return " ".join(parts)

def process_data(raw_data):
    if not raw_data:
        return pd.DataFrame(columns=['pid', 'name', 'state', 'cpu_percent', 'memory_mb', 'duration'])
    df = pd.DataFrame(raw_data)
    if not df.empty:
        current_time = time.time()
        df['duration'] = df['start_time'].apply(lambda x: format_duration(current_time - x) if x > 1000 else "N/A")
        df['cpu_percent'] = df['cpu_percent'].round(2)
        df['memory_mb'] = df['memory_mb'].round(2)
        df = df.drop(columns=['start_time'])
    return df

def terminate_process(pid):
    try:
        proc = psutil.Process(pid)
        proc.terminate()
        return True, f"Process {pid} terminated successfully."
    except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
        return False, f"Error terminating process {pid}: {str(e)}"

def get_process_details(pid):
    try:
        proc = psutil.Process(pid)
        details = {}
        # Attempt to fetch each attribute individually to handle AccessDenied
        try:
            details['start_time'] = proc.create_time()
        except psutil.AccessDenied:
            details['start_time'] = None
        try:
            details['user'] = proc.username()
        except psutil.AccessDenied:
            details['user'] = "Access Denied"
        try:
            details['threads'] = proc.num_threads()
        except psutil.AccessDenied:
            details['threads'] = "Access Denied"
        return details
    except psutil.NoSuchProcess:
        return {"error": f"Process {pid} has terminated."}
    except psutil.AccessDenied:
        return {"error": f"Access denied to process {pid} details. Try running the application as an administrator."}
    except Exception as e:
        return {"error": f"Unexpected error: {str(e)}"}