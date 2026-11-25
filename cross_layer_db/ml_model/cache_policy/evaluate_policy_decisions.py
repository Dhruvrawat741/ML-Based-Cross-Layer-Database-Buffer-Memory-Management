import csv
import json
import statistics
from collections import defaultdict
from pathlib import Path

from ml_policy import MLCachePolicy

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
OUTPUT = ROOT / "results"
OUTPUT.mkdir(exist_ok=True)

SNAPSHOT_FILE = DATA / "olist_page_snapshots_pressure.csv"
QUERY_FILE = DATA / "olist_2000_records.csv"
RESULT_FILE = OUTPUT / "ml_decision_results.csv"

policy = MLCachePolicy()

query_metrics = {}
with QUERY_FILE.open(newline="") as f:
    for row in csv.DictReader(f):
        query_metrics[int(row["record_id"])] = {
            "query_number": int(row["query_number"]),
            "execution_time_ms": float(row["execution_time_ms"]),
            "shared_hit_blocks": int(row["shared_hit_blocks"]),
            "shared_read_blocks": int(row["shared_read_blocks"]),
        }

history = {}
decisions = []

with SNAPSHOT_FILE.open(newline="") as source:
    reader = csv.DictReader(source)

    for snapshot_id, group in __import__("itertools").groupby(
        reader, key=lambda row: int(row["snapshot_id"])
    ):
        rows = list(group)
        record_id = int(rows[0]["record_id"])
        query = query_metrics[record_id]

        candidates = []

        for row in rows:
            page = row["page_id"]
            previous = history.get(page)

            if previous is None:
                recency = snapshot_id + 1
                first_seen = snapshot_id
                frequency = 0
            else:
                last_seen, first_seen, frequency = previous
                recency = snapshot_id - last_seen

            candidates.append({
                "page_id": page,
                "recency_snapshots": recency,
                "observed_frequency": frequency,
                "page_age_snapshots": snapshot_id - first_seen,
                "usage_count": int(row["usage_count"]),
                "is_dirty": int(str(row["dirty"]).lower() == "true"),
                "pin_count": int(row["pinned"]),
                **query,
            })

            history[page] = (
                snapshot_id,
                first_seen,
                frequency + 1
            )

        if snapshot_id == 1:
            continue

        decision = policy.choose_victim(candidates)

        decisions.append({
            "snapshot_id": snapshot_id,
            **decision,
        })

        if snapshot_id % 100 == 0:
            print(f"Evaluated {snapshot_id}/2000 snapshots")

with RESULT_FILE.open("w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=decisions[0].keys())
    writer.writeheader()
    writer.writerows(decisions)

latencies = [d["decision_latency_us"] for d in decisions]

summary = {
    "policy": "ML Random Forest",
    "decisions": len(decisions),
    "mean_decision_latency_us": statistics.mean(latencies),
    "median_decision_latency_us": statistics.median(latencies),
    "max_decision_latency_us": max(latencies),
    "mean_candidates": statistics.mean(
        d["candidates_considered"] for d in decisions
    ),
    "evaluation_type": "Snapshot-state victim scoring; not a cache hit-rate simulation."
}

(OUTPUT / "ml_decision_summary.json").write_text(
    json.dumps(summary, indent=4)
)

print("\n========== ML POLICY DECISION RESULTS ==========")
for key, value in summary.items():
    print(f"{key}: {value}")

print("\nSaved:", RESULT_FILE)
