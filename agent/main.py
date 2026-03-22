import time
import threading
import config
import heartbeat
import executor
import reporter
import requests

# Track how many jobs are currently running
# (used by heartbeat to report accurate job count)
jobs_running = 0
jobs_lock = threading.Lock()


def get_jobs_running() -> int:
    return jobs_running


def poll_for_jobs():
    """
    Main job polling loop.
    Every POLL_INTERVAL seconds, ask the platform:
    'Do you have a job for me?'
    If yes — run it.
    """
    global jobs_running

    print(f"[poller] Started — checking every {config.POLL_INTERVAL}s")

    while True:
        try:
            # Ask platform for next job
            response = requests.get(
                f"{config.PLATFORM_URL}/agent/pending-job",
                headers=config.AUTH_HEADERS,
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                job = data.get("job")

                if job:
                    job_id = job["id"]
                    print(f"\n[poller] Got job {job_id[:8]}!")

                    # Run job in a separate thread so polling continues
                    def run(j):
                        global jobs_running
                        with jobs_lock:
                            jobs_running += 1

                        try:
                            # Execute the job (Docker or simulation)
                            result = executor.run_job(j)

                            # Report completion to platform (triggers billing)
                            reporter.report_job_complete(
                                job_id=j["id"],
                                exit_code=result["exit_code"],
                                gpu_seconds_used=result["gpu_seconds_used"],
                                peak_vram_mb=result.get("peak_vram_mb"),
                            )

                        except Exception as e:
                            print(f"[poller] Job failed with exception: {e}")
                            reporter.report_job_complete(
                                job_id=j["id"],
                                exit_code=1,
                                gpu_seconds_used=0,
                                error_message=str(e),
                            )
                        finally:
                            with jobs_lock:
                                jobs_running -= 1

                    thread = threading.Thread(target=run, args=(job,), daemon=True)
                    thread.start()

                else:
                    print(f"[poller] No jobs waiting...")

            else:
                print(f"[poller] Error from platform: {response.status_code}")

        except Exception as e:
            print(f"[poller] Request failed: {e}")

        time.sleep(config.POLL_INTERVAL)


if __name__ == "__main__":
    print("=" * 50)
    print("GPU Agent starting...")
    print(f"Platform: {config.PLATFORM_URL}")
    print(f"API Key: {config.API_KEY[:20]}...")
    print("=" * 50)

    # Start heartbeat in background thread
    heartbeat.start_heartbeat_loop(get_jobs_running)

    # Send one immediate heartbeat so server shows online right away
    heartbeat.send_heartbeat(jobs_running=0)

    # Start job polling loop (runs forever in main thread)
    poll_for_jobs()