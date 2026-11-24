import csv
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import psutil

OUTPUT = Path(os.environ["ML_OS_OUTPUT"])
PHASE = os.environ["ML_PHASE"]
SAMPLES = int(os.environ["ML_OS_SAMPLES"])
INTERVAL = float(os.environ.get("ML_OS_INTERVAL", "2"))

FIELDS = [
    "timestamp_utc", "phase", "cpu_percent", "ram_percent",
    "ram_used_mb", "ram_available_mb", "swap_percent",
    "disk_read_bytes_total", "disk_write_bytes_total",
    "disk_read_bytes_per_sec", "disk_write_bytes_per_sec"
]


def main():
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    psutil.cpu_percent(interval=None)
    disk_previous = psutil.disk_io_counters()

    with OUTPUT.open("a", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDS)

        if OUTPUT.stat().st_size == 0:
            writer.writeheader()

        print(
            f"Phase: {PHASE} | Target: {SAMPLES} observations",
            flush=True
        )

        for i in range(SAMPLES):
            time.sleep(INTERVAL)

            now = datetime.now(timezone.utc).isoformat()
            cpu = psutil.cpu_percent(interval=None)
            memory = psutil.virtual_memory()
            swap = psutil.swap_memory()
            disk = psutil.disk_io_counters()

            read_rate = 0
            write_rate = 0

            if disk and disk_previous:
                read_rate = max(
                    0, disk.read_bytes - disk_previous.read_bytes
                ) / INTERVAL
                write_rate = max(
                    0, disk.write_bytes - disk_previous.write_bytes
                ) / INTERVAL

            writer.writerow({
                "timestamp_utc": now,
                "phase": PHASE,
                "cpu_percent": cpu,
                "ram_percent": memory.percent,
                "ram_used_mb": round(memory.used / 1048576, 2),
                "ram_available_mb": round(memory.available / 1048576, 2),
                "swap_percent": swap.percent,
                "disk_read_bytes_total": disk.read_bytes if disk else "",
                "disk_write_bytes_total": disk.write_bytes if disk else "",
                "disk_read_bytes_per_sec": round(read_rate, 2),
                "disk_write_bytes_per_sec": round(write_rate, 2)
            })

            file.flush()
            disk_previous = disk

            if (i + 1) % 25 == 0 or i + 1 == SAMPLES:
                print(f"{PHASE}: {i + 1}/{SAMPLES}", flush=True)

    print(f"Saved: {OUTPUT}", flush=True)


if __name__ == "__main__":
    main()
