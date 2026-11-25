import csv
import json
import statistics
from itertools import groupby
from pathlib import Path
from time import perf_counter_ns
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ml_model.cache_policy.ml_policy import MLCachePolicy

DATA = ROOT / "ml_model" / "cache_policy" / "data"
OUTPUT = ROOT / "page_replacement_benchmark" / "results"

SNAPSHOT_FILE = DATA / "olist_page_snapshots_pressure.csv"
QUERY_FILE = DATA / "olist_2000_records.csv"

RESULT_FILE = OUTPUT / "four_policy_eviction_results.csv"
SUMMARY_FILE = OUTPUT / "four_policy_eviction_summary.json"

FEATURES = [
    "recency_snapshots",
    "observed_frequency",
    "page_age_snapshots",
    "usage_count",
    "is_dirty",
    "pin_count",
    "query_number",
    "execution_time_ms",
    "shared_hit_blocks",
    "shared_read_blocks",
]


def load_query_metrics():
    metrics = {}

    with QUERY_FILE.open(newline="") as f:
        for row in csv.DictReader(f):
            metrics[int(row["record_id"])] = {
                "query_number": int(row["query_number"]),
                "execution_time_ms": float(row["execution_time_ms"]),
                "shared_hit_blocks": int(row["shared_hit_blocks"]),
                "shared_read_blocks": int(row["shared_read_blocks"]),
            }

    return metrics


def load_snapshots():
    snapshots = {}

    with SNAPSHOT_FILE.open(newline="") as f:
        reader = csv.DictReader(f)

        for snapshot_id, group in groupby(
            reader, key=lambda row: int(row["snapshot_id"])
        ):
            snapshots[int(snapshot_id)] = list(group)

    return snapshots


def evaluate():
    OUTPUT.mkdir(parents=True, exist_ok=True)

    print("Loading snapshots and query metrics...")
    snapshots = load_snapshots()
    query_metrics = load_query_metrics()

    if len(snapshots) < 2:
        raise ValueError("At least two snapshots are required.")

    ml_policy = MLCachePolicy()
    history = {}
    results = []

    policy_names = ["FIFO", "LRU", "LFU", "ML"]

    for snapshot_id in sorted(snapshots):
        next_id = snapshot_id + 1

        if next_id not in snapshots:
            continue

        current_rows = snapshots[snapshot_id]
        next_pages = {
            row["page_id"] for row in snapshots[next_id]
        }

        record_id = int(current_rows[0]["record_id"])

        if record_id not in query_metrics:
            raise KeyError(f"Missing query metrics for record {record_id}")

        query = query_metrics[record_id]
        candidates = []

        for row in current_rows:
            page = row["page_id"]
            previous = history.get(page)

            if previous is None:
                recency = snapshot_id + 1
                first_seen = snapshot_id
                frequency = 0
                last_seen = None
            else:
                last_seen, first_seen, frequency = previous
                recency = snapshot_id - last_seen

            candidate = {
                "page_id": page,
                "recency_snapshots": recency,
                "observed_frequency": frequency,
                "page_age_snapshots": snapshot_id - first_seen,
                "usage_count": int(row["usage_count"]),
                "is_dirty": int(
                    str(row["dirty"]).lower() == "true"
                ),
                "pin_count": int(row["pinned"]),
                **query,
                "_first_seen": first_seen,
                "_last_seen": last_seen,
            }

            candidates.append(candidate)

            history[page] = (
                snapshot_id,
                first_seen,
                frequency + 1,
            )

        eligible = [
            c for c in candidates if c["pin_count"] == 0
        ]

        if not eligible:
            continue

        actual_departures = {
            c["page_id"]
            for c in eligible
            if c["page_id"] not in next_pages
        }

        k = len(actual_departures)

        if k == 0:
            continue

        rankings = {}

        start = perf_counter_ns()
        rankings["FIFO"] = sorted(
            eligible,
            key=lambda c: (c["_first_seen"], c["page_id"]),
        )
        fifo_latency = (perf_counter_ns() - start) / 1000

        start = perf_counter_ns()
        rankings["LRU"] = sorted(
            eligible,
            key=lambda c: (
                c["_last_seen"] if c["_last_seen"] is not None
                else -1,
                c["page_id"],
            ),
        )
        lru_latency = (perf_counter_ns() - start) / 1000

        start = perf_counter_ns()
        rankings["LFU"] = sorted(
            eligible,
            key=lambda c: (
                c["observed_frequency"],
                c["_first_seen"],
                c["page_id"],
            ),
        )
        lfu_latency = (perf_counter_ns() - start) / 1000

        X = pd.DataFrame(eligible)[FEATURES]

        start = perf_counter_ns()
        probabilities = ml_policy.model.predict_proba(X)[:, 1]
        ml_latency = (perf_counter_ns() - start) / 1000

        rankings["ML"] = [
            candidate
            for _, candidate in sorted(
                zip(probabilities, eligible),
                key=lambda item: (
                    item[0],
                    item[1]["page_id"],
                ),
            )
        ]

        latencies = {
            "FIFO": fifo_latency,
            "LRU": lru_latency,
            "LFU": lfu_latency,
            "ML": ml_latency,
        }

        for policy in policy_names:
            predicted = {
                c["page_id"] for c in rankings[policy][:k]
            }

            correct = len(predicted & actual_departures)
            precision = correct / k
            recall = correct / len(actual_departures)
            f1 = (
                2 * precision * recall / (precision + recall)
                if precision + recall else 0
            )

            results.append({
                "snapshot_id": snapshot_id,
                "policy": policy,
                "candidates": len(eligible),
                "observed_departures": k,
                "correctly_ranked": correct,
                "precision_at_k": precision,
                "recall_at_k": recall,
                "f1_at_k": f1,
                "decision_latency_us": latencies[policy],
            })

        if snapshot_id % 100 == 0:
            print(f"Evaluated snapshot {snapshot_id}/{len(snapshots)}")

    if not results:
        raise RuntimeError("No snapshots had eligible observed departures.")

    with RESULT_FILE.open("w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=list(results[0].keys()),
        )
        writer.writeheader()
        writer.writerows(results)

    summary = {}

    for policy in policy_names:
        rows = [r for r in results if r["policy"] == policy]

        summary[policy] = {
            "evaluated_snapshots": len(rows),
            "mean_precision_at_k": statistics.mean(
                r["precision_at_k"] for r in rows
            ),
            "mean_recall_at_k": statistics.mean(
                r["recall_at_k"] for r in rows
            ),
            "mean_f1_at_k": statistics.mean(
                r["f1_at_k"] for r in rows
            ),
            "mean_decision_latency_us": statistics.mean(
                r["decision_latency_us"] for r in rows
            ),
        }

    summary["_methodology"] = {
        "evaluation": "Snapshot-based eviction ranking",
        "actual_victim_definition": (
            "Eligible pages present in snapshot t but absent in snapshot t+1"
        ),
        "k": (
            "Number of observed departures in the next snapshot; "
            "each policy predicts the same number of victims"
        ),
        "frequency_definition": (
            "Number of previous snapshots in which a page appeared; "
            "not exact logical access frequency"
        ),
        "limitation": (
            "This is not a logical page-reference trace or a cache "
            "hit-rate simulation. Snapshot departures may reflect "
            "buffer changes between observations."
        ),
    }

    SUMMARY_FILE.write_text(json.dumps(summary, indent=4))

    print("\n========== FOUR-POLICY EVICTION RANKING ==========")

    for policy in policy_names:
        values = summary[policy]
        print(f"\n{policy}")
        print(f"  Snapshots: {values['evaluated_snapshots']}")
        print(f"  Precision@K: {values['mean_precision_at_k']:.4f}")
        print(f"  Recall@K: {values['mean_recall_at_k']:.4f}")
        print(f"  F1@K: {values['mean_f1_at_k']:.4f}")
        print(
            "  Mean latency: "
            f"{values['mean_decision_latency_us']:.2f} us"
        )

    print("\nResults saved:")
    print(RESULT_FILE)
    print(SUMMARY_FILE)


if __name__ == "__main__":
    evaluate()
