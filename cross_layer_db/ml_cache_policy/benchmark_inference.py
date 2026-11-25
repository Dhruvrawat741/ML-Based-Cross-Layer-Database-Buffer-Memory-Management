import statistics
import time
import pandas as pd
import joblib

from pathlib import Path

ROOT = Path(__file__).resolve().parent

MODEL = joblib.load(
    ROOT / "models" / "ml_cache_policy_random_forest.joblib"
)

DATA = pd.read_csv(
    ROOT / "data" / "cache_policy_training_data.csv"
)

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

def benchmark(frame_count, repeats=100):
    sample = DATA[FEATURES].tail(frame_count).copy()

    # Warm up model
    MODEL.predict_proba(sample)

    times = []

    for _ in range(repeats):
        start = time.perf_counter_ns()
        MODEL.predict_proba(sample)
        elapsed = (time.perf_counter_ns() - start) / 1_000_000
        times.append(elapsed)

    return {
        "frames": frame_count,
        "mean_ms": statistics.mean(times),
        "median_ms": statistics.median(times),
        "p95_ms": sorted(times)[int(0.95 * (len(times) - 1))],
    }


print("========== INFERENCE BENCHMARK ==========")

for frames in [64, 128, 256, 512, 2024]:
    result = benchmark(frames)
    print(
        f"Frames: {result['frames']:4} | "
        f"Mean: {result['mean_ms']:.4f} ms | "
        f"Median: {result['median_ms']:.4f} ms | "
        f"P95: {result['p95_ms']:.4f} ms"
    )
