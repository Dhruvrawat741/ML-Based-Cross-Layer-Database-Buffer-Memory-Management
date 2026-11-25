
from collections import deque


class PageReplacementSimulator:
    """FIFO, LRU and LFU page replacement with performance metrics."""

    def __init__(self, policy, capacity):
        if policy not in {"FIFO", "LRU", "LFU"}:
            raise ValueError("Policy must be FIFO, LRU or LFU")
        if capacity < 1:
            raise ValueError("Capacity must be at least 1")

        self.policy = policy
        self.capacity = capacity
        self.frames = set()
        self.order = deque()       # FIFO order
        self.last_used = {}        # LRU timestamps
        self.frequency = {}        # LFU counts
        self.last_loaded = {}      # LFU tie-break: oldest loaded page
        self.clock = 0

        self.hits = 0
        self.faults = 0
        self.replacements = 0
        self.replacement_time_ns = 0

    def access(self, page):
        self.clock += 1

        if page in self.frames:
            self.hits += 1
            self.frequency[page] += 1
            self.last_used[page] = self.clock
            return

        self.faults += 1

        if len(self.frames) >= self.capacity:
            start = __import__("time").perf_counter_ns()

            if self.policy == "FIFO":
                victim = self.order.popleft()
            elif self.policy == "LRU":
                victim = min(self.frames, key=self.last_used.get)
            else:  # LFU; ties are broken by oldest load time
                victim = min(
                    self.frames,
                    key=lambda p: (self.frequency[p], self.last_loaded[p]),
                )

            self.replacement_time_ns += (
                __import__("time").perf_counter_ns() - start
            )
            self.frames.remove(victim)
            self.last_used.pop(victim)
            self.frequency.pop(victim)
            self.last_loaded.pop(victim)
            self.replacements += 1

        self.frames.add(page)
        self.order.append(page)
        self.last_used[page] = self.clock
        self.frequency[page] = 1
        self.last_loaded[page] = self.clock

    def run(self, trace):
        import time

        start = time.perf_counter_ns()
        for page in trace:
            self.access(page)
        total_time_ns = time.perf_counter_ns() - start

        total = self.hits + self.faults
        return {
            "policy": self.policy,
            "frame_capacity": self.capacity,
            "references": total,
            "page_hits": self.hits,
            "page_faults": self.faults,
            "hit_ratio": self.hits / total if total else 0,
            "fault_ratio": self.faults / total if total else 0,
            "replacements": self.replacements,
            "replacement_time_us": self.replacement_time_ns / 1000,
            "total_simulation_time_ms": total_time_ns / 1_000_000,
        }
