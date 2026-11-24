from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from ml_cache_policy.ml_policy import MLCachePolicy


class MLPolicySimulator:
    """
    Adapter for the trained snapshot-based ML eviction policy.

    Unlike FIFO/LRU/LFU, this policy requires snapshot-derived
    candidate features. It cannot consume a page-reference trace
    directly without a compatible feature-generation pipeline.
    """

    def __init__(self, capacity):
        if capacity < 1:
            raise ValueError("Capacity must be at least 1")

        self.capacity = capacity
        self.policy = MLCachePolicy()

    def choose_victim(self, candidates):
        if len(candidates) <= self.capacity:
            raise ValueError(
                "Victim selection requires more candidates than capacity."
            )

        return self.policy.choose_victim(candidates)
