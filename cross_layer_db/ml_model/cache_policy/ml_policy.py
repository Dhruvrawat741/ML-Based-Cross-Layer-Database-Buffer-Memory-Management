import joblib
import pandas as pd
from pathlib import Path
from time import perf_counter_ns

ROOT = Path(__file__).resolve().parent
MODEL_PATH = ROOT / "models" / "ml_cache_policy_random_forest_optimized.joblib"

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


class MLCachePolicy:
    def __init__(self, model_path=MODEL_PATH):
        self.model = joblib.load(model_path)

    def choose_victim(self, candidates):
        """
        candidates: list of dictionaries containing page_id
        and the ten model features.

        Returns the selected victim and decision latency.
        """
        if not candidates:
            raise ValueError("No eviction candidates available.")

        eligible = [
            page for page in candidates
            if int(page["pin_count"]) == 0
        ]

        if not eligible:
            raise RuntimeError("All candidate pages are pinned.")

        X = pd.DataFrame(eligible)[FEATURES]

        start = perf_counter_ns()
        probabilities = self.model.predict_proba(X)[:, 1]
        latency_us = (perf_counter_ns() - start) / 1000

        scored = [
            {
                "page_id": page["page_id"],
                "predicted_residency_probability": float(probability),
            }
            for page, probability in zip(eligible, probabilities)
        ]

        victim = min(
            scored,
            key=lambda item: item["predicted_residency_probability"]
        )

        return {
            **victim,
            "decision_latency_us": latency_us,
            "candidates_considered": len(eligible),
        }
