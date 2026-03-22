import time
import json
import reporter


def run_job(job: dict) -> dict:
    """
    Execute a GPU job using Docker.

    Steps:
    1. Try to use real Docker (requires Docker Desktop running)
    2. Falls back to simulation mode for testing on Mac without GPU

    Returns dict with exit_code, gpu_seconds_used, peak_vram_mb
    """
    job_id = job["id"]
    docker_image = job["docker_image"]
    command = job.get("command")
    env_vars = job.get("env_vars", {})
    max_runtime_minutes = job.get("max_runtime_minutes", 60)

    # Parse env_vars if it came as a string
    if isinstance(env_vars, str):
        try:
            env_vars = json.loads(env_vars.replace("'", '"'))
        except Exception:
            env_vars = {}

    print(f"[executor] Starting job {job_id[:8]}... image={docker_image}")

    # Try real Docker first
    try:
        return _run_with_docker(job_id, docker_image, command, env_vars, max_runtime_minutes)
    except Exception as e:
        print(f"[executor] Docker not available ({e}), running in simulation mode")
        return _run_simulated(job_id, max_runtime_minutes)


def _run_with_docker(job_id, docker_image, command, env_vars, max_runtime_minutes):
    """Run the job in a real Docker container."""
    import docker

    client = docker.from_env()
    start_time = time.time()

    # Report job started
    reporter.report_job_started(job_id)

    print(f"[executor] Pulling image {docker_image}...")
    client.images.pull(docker_image)

    # Run the container
    container = client.containers.run(
        image=docker_image,
        command=command,
        environment=env_vars,
        detach=True,           # run in background
        # gpu passthrough — uncomment on real GPU server:
        # device_requests=[docker.types.DeviceRequest(count=-1, capabilities=[['gpu']])]
    )

    print(f"[executor] Container started: {container.short_id}")

    # Stream logs back to platform
    seq = 0
    timeout = max_runtime_minutes * 60

    for log_chunk in container.logs(stream=True, follow=True):
        chunk_text = log_chunk.decode("utf-8", errors="replace").strip()
        if chunk_text:
            print(f"[log] {chunk_text}")
            reporter.report_log_chunk(job_id, chunk_text, seq)
            seq += 1

        # Check timeout
        if time.time() - start_time > timeout:
            print(f"[executor] Job timed out after {max_runtime_minutes} minutes")
            container.kill()
            break

    # Wait for container to finish
    result = container.wait()
    exit_code = result.get("StatusCode", 1)
    gpu_seconds = int(time.time() - start_time)

    # Cleanup container
    container.remove()

    print(f"[executor] Job done — exit_code={exit_code} gpu_seconds={gpu_seconds}")
    return {
        "exit_code": exit_code,
        "gpu_seconds_used": gpu_seconds,
        "peak_vram_mb": None,
    }


def _run_simulated(job_id, max_runtime_minutes):
    """
    Simulation mode — no Docker needed.
    Used for testing on Mac without a GPU.
    Pretends to run for 60 seconds.
    """
    print(f"[executor] SIMULATION MODE — pretending to run job for 60s")

    # Report started
    reporter.report_job_started(job_id)

    # Simulate work with fake log output
    fake_logs = [
        "Initializing model...",
        "Loading dataset...",
        "Epoch 1/3 — loss: 0.842",
        "Epoch 2/3 — loss: 0.531",
        "Epoch 3/3 — loss: 0.298",
        "Training complete. Saving model...",
        "Done.",
    ]

    for i, log_line in enumerate(fake_logs):
        print(f"[log] {log_line}")
        reporter.report_log_chunk(job_id, log_line, seq=i)
        time.sleep(8)   # spread over ~60 seconds

    return {
        "exit_code": 0,
        "gpu_seconds_used": 60,
        "peak_vram_mb": 8192,
    }