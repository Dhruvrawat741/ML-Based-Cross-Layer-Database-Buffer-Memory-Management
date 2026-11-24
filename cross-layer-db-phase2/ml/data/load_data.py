import csv
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data" / "OS_result"


def load_csv(filename):
    file_path = DATA_DIR / filename

    if not file_path.exists():
        print(f"[WARNING] Missing file: {file_path}")
        return []

    with file_path.open("r", newline="") as file:
        return list(csv.DictReader(file))


def validate_trace(rows):
    required = {"timestamp_ns", "pid", "event_type"}

    if not rows:
        print("[WARNING] Page trace is empty.")
        return False

    missing = required - set(rows[0].keys())

    if missing:
        print(f"[ERROR] Missing trace columns: {missing}")
        return False

    print(f"[OK] Page trace: {len(rows)} events")
    return True


def main():
    page_trace = load_csv("page_access_trace.csv")
    os_metrics = load_csv("query_workload_data.csv")
    query_metrics = load_csv("query_metrics.csv")

    print("\n========== DATA INGESTION REPORT ==========")

    validate_trace(page_trace)

    print(f"OS metric records: {len(os_metrics)}")
    print(f"Query metric records: {len(query_metrics)}")

    if os_metrics:
        print("OS columns:", list(os_metrics[0].keys()))

    if query_metrics:
        print("Query columns:", list(query_metrics[0].keys()))

    print("\nData ingestion completed.")


if __name__ == "__main__":
    main()
