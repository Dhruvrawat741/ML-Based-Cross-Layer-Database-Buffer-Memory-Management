import statistics
import time
import joblib
import pandas as pd

from pathlib import Path
from threadpoolctl import threadpool_limits

ROOT = Path(__file__).resolve().parent

model = joblib.load(
    ROOT / "models" / "ml_cache_policy_random_forest.joblib"
)

data = pd.read_csv(
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

print("Model trees:", model.n_estimators)
print("Model max depth:", model.max_depth)
print("Original n_jobs:", model.n_jobs)

for jobs in [-1, 1]:
    model.n_jobs = jobs

    print(f"\n========== n_jobs={jobs} ==========")

    with threadpool_limits(limits=1):
        for frames in [64, 128, 256, 512]:
            X = data[FEATURES].tail(frames)

            # Warm-up
            model.predict_proba(X)

            timings = []

            for _ in range(50):
                start = time.perf_counter_ns()
                model.predict_proba(X)
                timings.append(
                    (time.perf_counter_ns() - start) / 1_000_000
                )

            print(
                f"{frames:4} candidates | "
                f"Mean: {statistics.mean(timings):.3f} ms | "
                f"Median: {statistics.median(timings):.3f} ms"
            )
