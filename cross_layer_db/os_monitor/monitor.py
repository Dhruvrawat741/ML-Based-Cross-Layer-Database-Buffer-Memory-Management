
import csv
import os
import time
from datetime import datetime, timezone

import psutil

OUTPUT_DIR = "data/OS_result"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "query_workload_data.csv")
INTERVAL_SECONDS = 2

FIELDS = [
    "timestamp_utc",
    "cpu_percent",
    "ram_percent",
    "ram_used_mb",
    "ram_available_mb",
    "swap_percent",
    "disk_read_bytes_total",
    "disk_write_bytes_total",
    "disk_read_bytes_per_sec",
    "disk_write_bytes_per_sec",
]

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    disk_previous = psutil.disk_io_counters()

    # Prime CPU measurement so the next reading is meaningful.
    psutil.cpu_percent(interval=None)
    time.sleep(INTERVAL_SECONDS)
    file_exists = os.path.exists(OUTPUT_FILE)
    with open(OUTPUT_FILE, "a", newline="") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=FIELDS)

        if not file_exists or os.path.getsize(OUTPUT_FILE) == 0:
            writer.writeheader()

        print(f"Collecting OS metrics every {INTERVAL_SECONDS}s.")
        print(f"Saving to: {OUTPUT_FILE}")
        print("Press Ctrl+C to stop.")

        try:
            while True:
                timestamp = datetime.now(timezone.utc).isoformat()
                cpu = psutil.cpu_percent(interval=None)
                memory = psutil.virtual_memory()
                swap = psutil.swap_memory()
                disk_current = psutil.disk_io_counters()

                elapsed = INTERVAL_SECONDS
                read_rate = 0
                write_rate = 0

                if disk_previous and disk_current:
                    read_rate = (
                        disk_current.read_bytes - disk_previous.read_bytes
                    ) / elapsed
                    write_rate = (
                        disk_current.write_bytes - disk_previous.write_bytes
                    ) / elapsed

                writer.writerow({
                    "timestamp_utc": timestamp,
                    "cpu_percent": cpu,
                    "ram_percent": memory.percent,
                    "ram_used_mb": round(memory.used / (1024 ** 2), 2),
                    "ram_available_mb": round(
                        memory.available / (1024 ** 2), 2
                    ),
                    "swap_percent": swap.percent,
                    "disk_read_bytes_total": (
                        disk_current.read_bytes if disk_current else ""
                    ),
                    "disk_write_bytes_total": (
                        disk_current.write_bytes if disk_current else ""
                    ),
                    "disk_read_bytes_per_sec": round(max(read_rate, 0), 2),
                    "disk_write_bytes_per_sec": round(max(write_rate, 0), 2),
                })

                csvfile.flush()
                disk_previous = disk_current

                print(
                    f"CPU: {cpu:5.1f}% | "
                    f"RAM: {memory.percent:5.1f}% | "
                    f"Available RAM: {memory.available / (1024 ** 2):.0f} MB"
                )

                time.sleep(INTERVAL_SECONDS)

        except KeyboardInterrupt:
            print("\nCollection stopped.")

if __name__ == "__main__":
    main()
