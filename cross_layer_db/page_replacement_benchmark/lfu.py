from time import perf_counter_ns


class LFUSimulator:
    def __init__(self, capacity):
        if capacity < 1:
            raise ValueError("Capacity must be at least 1")

        self.capacity = capacity
        self.frames = set()
        self.frequency = {}
        self.last_loaded = {}
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
            return

        self.faults += 1

        if len(self.frames) >= self.capacity:
            start = perf_counter_ns()
            victim = min(
                self.frames,
                key=lambda p: (self.frequency[p], self.last_loaded[p])
            )
            self.replacement_time_ns += perf_counter_ns() - start

            self.frames.remove(victim)
            self.frequency.pop(victim)
            self.last_loaded.pop(victim)
            self.replacements += 1

        self.frames.add(page)
        self.frequency[page] = 1
        self.last_loaded[page] = self.clock

    def run(self, trace):
        start = perf_counter_ns()

        for page in trace:
            self.access(page)

        total_time_ns = perf_counter_ns() - start
        total = self.hits + self.faults

        return {
            "policy": "LFU",
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
