from collections import deque
from time import perf_counter_ns


class FIFOSimulator:
    def __init__(self, capacity):
        if capacity < 1:
            raise ValueError("Capacity must be at least 1")

        self.capacity = capacity
        self.frames = set()
        self.order = deque()
        self.hits = 0
        self.faults = 0
        self.replacements = 0
        self.replacement_time_ns = 0

    def access(self, page):
        if page in self.frames:
            self.hits += 1
            return

        self.faults += 1

        if len(self.frames) >= self.capacity:
            start = perf_counter_ns()
            victim = self.order.popleft()
            self.replacement_time_ns += perf_counter_ns() - start

            self.frames.remove(victim)
            self.replacements += 1

        self.frames.add(page)
        self.order.append(page)

    def run(self, trace):
        start = perf_counter_ns()

        for page in trace:
            self.access(page)

        total_time_ns = perf_counter_ns() - start
        total = self.hits + self.faults

        return {
            "policy": "FIFO",
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
