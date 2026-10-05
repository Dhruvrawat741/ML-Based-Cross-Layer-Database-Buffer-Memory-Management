import psutil
import csv
from datetime import datetime
import os

OUTPUT_FILE = "data/raw/os_metrics.csv"

os.makedirs("data/raw", exist_ok=True)

with open(OUTPUT_FILE, "w", newline="") as file:
    writer = csv.writer(file)

    writer.writerow([
        "timestamp",
        "cpu_percent",
        "ram_percent",
        "available_ram_mb",
        "disk_read_mb",
        "disk_write_mb"
    ])

    print("OS monitoring started...")
    print("Press Ctrl+C to stop.")

    previous_disk = psutil.disk_io_counters()

    try:
        while True:
            cpu = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            current_disk = psutil.disk_io_counters()

            read_mb = (
                current_disk.read_bytes - previous_disk.read_bytes
            ) / (1024 * 1024)

            write_mb = (
                current_disk.write_bytes - previous_disk.write_bytes
            ) / (1024 * 1024)

            previous_disk = current_disk

            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            writer.writerow([
                timestamp,
                cpu,
                memory.percent,
                round(memory.available / (1024 * 1024), 2),
                round(read_mb, 2),
                round(write_mb, 2)
            ])

            file.flush()

            print(
                f"{timestamp} | "
                f"CPU: {cpu}% | "
                f"RAM: {memory.percent}% | "
                f"Disk Read: {read_mb:.2f} MB | "
                f"Disk Write: {write_mb:.2f} MB"
            )

    except KeyboardInterrupt:
        print("\nOS monitoring stopped.")
