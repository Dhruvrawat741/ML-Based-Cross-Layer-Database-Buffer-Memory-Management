from time import perf_counter_ns


class LRUSimulator:
    def __init__(self, capacity):
        if capacity < 1:
            raise ValueError("Capacity must be at least 1")

        self.capacity = capacity
        self.frames = set()
        self.last_used = {}
        self.clock = 0
        self.hits = 0
        self.faults = 0
        self.replacements = 0
        self.replacement_time_ns = 0

    def access(self, page):
        self.clock += 1

        if page in self.frames:
            self.hits += 1
            self.last_used[page] = self.clock
            return

        self.faults += 1

        if len(self.frames) >= self.capacity:
            start = perf_counter_ns()
            victim = min(self.frames, key=self.last_used.get)
            self.replacement_time_ns += perf_counter_ns() - start

            self.frames.remove(victim)
            self.last_used.pop(victim)
            self.replacements += 1

        self.frames.add(page)
        self.last_used[page] = self.clock

    def run(self, trace):
        start = perf_counter_ns()

        for page in trace:
            self.access(page)

        total_time_ns = perf_counter_ns() - start
        total = self.hits + self.faults

        return {
            "policy": "LRU",
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
