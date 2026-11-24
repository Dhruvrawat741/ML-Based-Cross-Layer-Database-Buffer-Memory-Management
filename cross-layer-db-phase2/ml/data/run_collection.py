import csv
import os
import re
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE_DIR = ROOT / "data" / "OS_result"

PHASES = [
    ("idle", 800, 0),
    ("light", 1600, 60),
    ("heavy", 1600, 0),
]

INTERVAL = 2
QUERY_SCRIPT = ROOT / "experiments" / "measure_query_metrics.py"
OS_MODULE = "ml.data.collect_os_metrics"

PROBE = (
    'usdt:/usr/lib/postgresql/18/bin/postgres:postgresql:'
    'buffer__read__start '
    '{ printf("%llu,%d,buffer_read_start\\n", nsecs, pid); }'
)


def run_query_batch(phase, query_file):
    env = os.environ.copy()
    env["ML_PHASE"] = phase
    env["ML_QUERY_OUTPUT"] = str(query_file)

    print(f"\nRunning Olist query batch: {phase}", flush=True)

    subprocess.run(
        [sys.executable, str(QUERY_SCRIPT)],
        cwd=ROOT,
        env=env,
        check=True,
    )


def collect_phase(phase, samples, query_interval, output_file, query_file):
    env = os.environ.copy()
    env["ML_PHASE"] = phase
    env["ML_OS_SAMPLES"] = str(samples)
    env["ML_OS_INTERVAL"] = str(INTERVAL)
    env["ML_OS_OUTPUT"] = str(output_file)

    print(f"\n{'=' * 55}")
    print(f"STARTING {phase.upper()} PHASE: {samples} observations")
    print(f"{'=' * 55}", flush=True)

    monitor = subprocess.Popen(
        [sys.executable, "-m", OS_MODULE],
        cwd=ROOT,
        env=env,
    )

    next_query = time.monotonic()

    try:
        while monitor.poll() is None:
            now = time.monotonic()

            if phase != "idle" and now >= next_query:
                run_query_batch(phase, query_file)

                if query_interval > 0:
                    next_query = time.monotonic() + query_interval
                else:
                    next_query = time.monotonic()

            time.sleep(0.2)

        if monitor.returncode != 0:
            raise RuntimeError(f"OS monitor failed during {phase} phase")

    except BaseException:
        monitor.terminate()
        monitor.wait()
        raise

    print(f"\n{phase.upper()} phase completed.", flush=True)


def stop_tracer(tracer):
    if tracer is None or tracer.poll() is not None:
        return

    tracer.send_signal(signal.SIGINT)

    try:
        tracer.wait(timeout=10)
    except subprocess.TimeoutExpired:
        tracer.terminate()
        tracer.wait()


def convert_trace(raw_file, csv_file):
    count = 0

    with raw_file.open("r", errors="replace") as source, \
         csv_file.open("w", newline="") as target:

        writer = csv.writer(target)
        writer.writerow(["timestamp_ns", "pid", "event_type"])

        for line in source:
            parts = line.strip().split(",")

            if (
                len(parts) == 3
                and parts[0].isdigit()
                and parts[1].isdigit()
            ):
                writer.writerow(parts)
                count += 1

    return count


def main():
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = BASE_DIR / f"ml_collection_{run_id}"
    run_dir.mkdir(parents=True, exist_ok=False)

    os_file = run_dir / "os_metrics.csv"
    query_file = run_dir / "query_metrics.csv"
    trace_file = run_dir / "page_access_trace.csv"
    raw_trace = run_dir / "page_trace_raw.txt"

    total_samples = sum(samples for _, samples, _ in PHASES)
    tracer = None

    print("ML CROSS-LAYER DATA COLLECTION")
    print(f"Experiment directory: {run_dir}")
    print(f"Target OS observations: {total_samples}")
    print(f"Sampling interval: {INTERVAL} seconds")
    print("Workload phases: idle, light, heavy")

    try:
        # Authenticate sudo before starting the tracer.
        subprocess.run(["sudo", "-v"], check=True)

        tracer = subprocess.Popen([
            "sudo",
            "bpftrace",
            "-o", str(raw_trace),
            "-e", PROBE,
        ])

        time.sleep(2)

        if tracer.poll() is not None:
            raise RuntimeError("PostgreSQL bpftrace probe failed to start")

        for phase, samples, query_interval in PHASES:
            collect_phase(
                phase,
                samples,
                query_interval,
                os_file,
                query_file,
            )

        print("\nAll workload phases completed.")

    except KeyboardInterrupt:
        print("\nCollection interrupted by user.")

    finally:
        stop_tracer(tracer)

        if raw_trace.exists():
            trace_count = convert_trace(raw_trace, trace_file)
            print(f"Captured PostgreSQL buffer-read events: {trace_count}")

    if os_file.exists():
        with os_file.open() as file:
            os_count = sum(1 for _ in file) - 1
        print(f"OS observations collected: {os_count}")

    if query_file.exists():
        with query_file.open() as file:
            query_count = sum(1 for _ in file) - 1
        print(f"Query executions collected: {query_count}")

    print(f"\nExperiment files saved in:\n{run_dir}")


if __name__ == "__main__":
    main()
