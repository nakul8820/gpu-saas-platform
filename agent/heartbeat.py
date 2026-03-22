import requests
import psutil
import time
import threading
import config

def get_gpu_metrics() -> dict:
    """
    Try to get real GPU metrics using nvidia-smi.
    Falls back to zeros if no GPU available (for testing on Mac).

    In production on a real GPU server, nvidia-smi is always available.
    """
    try:
        import subprocess
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=utilization.gpu,memory.used,memory.free,temperature.gpu",
                "--format=csv,noheader,nounits"
            ],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            parts = result.stdout.strip().split(", ")
            return {
                "gpu_pct": int(parts[0]),
                "vram_used_mb": int(parts[1]),
                "vram_free_mb": int(parts[2]),
                "temp_celsius": int(parts[3]),
            }
    except Exception:
        pass

    # No GPU available — return simulated values for testing
    return {
        "gpu_pct": 0,
        "vram_used_mb": 0,
        "vram_free_mb": 80000,
        "temp_celsius": 0,
    }


def send_heartbeat(jobs_running: int = 0):
    """
    Send current server metrics to the platform.
    Called every HEARTBEAT_INTERVAL seconds.
    """
    gpu = get_gpu_metrics()
    cpu_pct = psutil.cpu_percent(interval=1)

    payload = {
        "cpu_pct": int(cpu_pct),
        "gpu_pct": gpu["gpu_pct"],
        "vram_used_mb": gpu["vram_used_mb"],
        "vram_free_mb": gpu["vram_free_mb"],
        "temp_celsius": gpu["temp_celsius"],
        "jobs_running": jobs_running,
    }

    try:
        response = requests.post(
            f"{config.PLATFORM_URL}/agent/heartbeat",
            json=payload,
            headers=config.AUTH_HEADERS,
            timeout=10
        )
        if response.status_code == 200:
            print(f"[heartbeat] OK — CPU:{cpu_pct}% GPU:{gpu['gpu_pct']}%")
        else:
            print(f"[heartbeat] Failed: {response.status_code} {response.text}")
    except Exception as e:
        print(f"[heartbeat] Error: {e}")


def start_heartbeat_loop(get_jobs_running):
    """
    Run heartbeat in a background thread forever.
    get_jobs_running is a function that returns current job count.
    """
    def loop():
        while True:
            send_heartbeat(jobs_running=get_jobs_running())
            time.sleep(config.HEARTBEAT_INTERVAL)

    thread = threading.Thread(target=loop, daemon=True)
    thread.start()
    print(f"[heartbeat] Started — sending every {config.HEARTBEAT_INTERVAL}s")