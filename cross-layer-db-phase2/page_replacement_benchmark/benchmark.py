
import csv
import random
import tracemalloc
from pathlib import Path

from algorithms import PageReplacementSimulator

ROOT = Path(__file__).resolve().parent.parent
DATASET = ROOT / "data/processed/page_access_dataset.csv"
OUTPUT = ROOT / "page_replacement_benchmark/results/benchmark_results.csv"

POLICIES = ["FIFO", "LRU", "LFU"]
CAPACITIES = [8, 16, 32, 64]
REPEATS = 5


def load_trace():
    if not DATASET.exists():
        raise FileNotFoundError(
            f"{DATASET} not found. Run ml/generate_dataset.py first."
        )

    with DATASET.open(newline="") as f:
        rows = list(csv.DictReader(f))

    rows.sort(key=lambda row: int(row["position"]))
    trace = [int(row["page_id"]) for row in rows]

    if not trace:
        raise ValueError("The page-reference trace is empty.")

    return trace


def main():
    trace = load_trace()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    fields = [
        "policy", "frame_capacity", "repeat",
        "references", "page_hits", "page_faults",
        "hit_ratio", "fault_ratio", "replacements",
        "replacement_time_us", "total_simulation_time_ms",
        "peak_python_memory_kb",
    ]

    rows = []

    for capacity in CAPACITIES:
        for policy in POLICIES:
            for repeat in range(1, REPEATS + 1):
                simulator = PageReplacementSimulator(policy, capacity)

                tracemalloc.start()
                result = simulator.run(trace)
                _, peak_memory = tracemalloc.get_traced_memory()
                tracemalloc.stop()

                result["repeat"] = repeat
                result["peak_python_memory_kb"] = peak_memory / 1024
                rows.append(result)

                print(
                    f"{policy:4} | frames={capacity:2} | "
                    f"run={repeat} | faults={result['page_faults']:5} | "
                    f"hits={result['page_hits']:5} | "
                    f"hit ratio={result['hit_ratio']:.3f} | "
                    f"time={result['total_simulation_time_ms']:.3f} ms"
                )

    with OUTPUT.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nTrace length: {len(trace)}")
    print(f"Unique pages: {len(set(trace))}")
    print(f"Results saved to: {OUTPUT}")


if __name__ == "__main__":
    main()
