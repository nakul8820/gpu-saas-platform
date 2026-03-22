import requests
import config


def report_job_started(job_id: str):
    """Tell the platform the Docker container has started."""
    try:
        response = requests.post(
            f"{config.PLATFORM_URL}/agent/job-start",
            json={"job_id": job_id},
            headers=config.AUTH_HEADERS,
            timeout=10
        )
        if response.status_code == 200:
            print(f"[reporter] Job {job_id[:8]}... marked as running")
        else:
            print(f"[reporter] job-start failed: {response.text}")
    except Exception as e:
        print(f"[reporter] job-start error: {e}")


def report_log_chunk(job_id: str, chunk: str, seq: int, stream: str = "stdout"):
    """Stream a chunk of stdout/stderr back to the platform."""
    try:
        requests.post(
            f"{config.PLATFORM_URL}/agent/job-log",
            params={
                "job_id": job_id,
                "chunk": chunk,
                "seq": seq,
                "stream": stream,
            },
            headers=config.AUTH_HEADERS,
            timeout=5
        )
    except Exception as e:
        print(f"[reporter] log chunk error: {e}")


def report_job_complete(
    job_id: str,
    exit_code: int,
    gpu_seconds_used: int,
    peak_vram_mb: int = None,
    error_message: str = None
):
    """
    Tell the platform the job finished.
    This triggers billing reconciliation on the platform side.
    """
    payload = {
        "job_id": job_id,
        "exit_code": exit_code,
        "gpu_seconds_used": gpu_seconds_used,
        "peak_vram_mb": peak_vram_mb,
        "error_message": error_message,
    }

    try:
        response = requests.post(
            f"{config.PLATFORM_URL}/agent/job-complete",
            json=payload,
            headers=config.AUTH_HEADERS,
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            print(f"[reporter] Job complete — billed {data.get('tokens_billed')} tokens, refunded {data.get('tokens_refunded')}")
        else:
            print(f"[reporter] job-complete failed: {response.text}")
    except Exception as e:
        print(f"[reporter] job-complete error: {e}")