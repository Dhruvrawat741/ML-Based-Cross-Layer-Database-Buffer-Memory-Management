
import csv
import os
import statistics

FILES = {
    "Idle": "data/OS_result/idle_data.csv",
    "Database workload": "data/OS_result/query_workload_data.csv",
}

METRICS = {
    "CPU usage (%)": ("cpu_percent", 1),
    "RAM usage (%)": ("ram_percent", 1),
    "RAM used (MB)": ("ram_used_mb", 1),
    "Available RAM (MB)": ("ram_available_mb", 1),
    "Swap usage (%)": ("swap_percent", 1),
    "Disk read rate (MB/s)": ("disk_read_bytes_per_sec", 1 / (1024 ** 2)),
    "Disk write rate (MB/s)": ("disk_write_bytes_per_sec", 1 / (1024 ** 2)),
}

def load_csv(path):
    with open(path, newline="") as file:
        return list(csv.DictReader(file))

def main():
    results = {}

    for label, path in FILES.items():
        if not os.path.exists(path):
            print(f"Missing file: {path}")
            return

        rows = load_csv(path)
        if not rows:
            print(f"No data in: {path}")
            return

        results[label] = rows

    print("\nOS METRICS COMPARISON")
    print("=" * 88)
    print(f"{'Metric':<29}{'Idle average':>18}{'Workload average':>23}")
    print("-" * 88)

    for metric, (column, multiplier) in METRICS.items():
        averages = {}

        for label, rows in results.items():
            values = []

            for row in rows:
                try:
                    value = float(row[column])
                    values.append(value * multiplier)
                except (ValueError, KeyError, TypeError):
                    continue

            averages[label] = (
                statistics.mean(values) if values else None
            )

        idle = averages["Idle"]
        workload = averages["Database workload"]

        idle_text = f"{idle:.2f}" if idle is not None else "No data"
        workload_text = (
            f"{workload:.2f}" if workload is not None else "No data"
        )

        print(f"{metric:<29}{idle_text:>18}{workload_text:>23}")

    print("\nSAMPLE COUNTS")
    for label, rows in results.items():
        print(f"{label}: {len(rows)} measurements")

if __name__ == "__main__":
    main()
