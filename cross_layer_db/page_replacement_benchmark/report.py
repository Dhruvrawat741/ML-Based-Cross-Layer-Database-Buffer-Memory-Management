
import csv
import statistics
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent
INPUT = ROOT / "results" / "benchmark_results.csv"
OUT = ROOT / "results"
SUMMARY_CSV = OUT / "summary.csv"
REPORT_MD = OUT / "benchmark_report.md"

METRICS = [
    ("page_faults", "Average page faults", "Page faults"),
    ("hit_ratio", "Average hit ratio", "Hit ratio"),
    ("total_simulation_time_ms", "Total simulation time", "Time (ms)"),
    ("replacement_time_us", "Replacement decision time", "Time (µs)"),
    ("peak_python_memory_kb", "Peak traced Python memory", "Memory (KB)"),
]

def mean(values):
    return statistics.mean(values)

def load_results():
    if not INPUT.exists():
        raise FileNotFoundError(f"Benchmark CSV not found: {INPUT}")

    with INPUT.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    if not rows:
        raise ValueError("Benchmark CSV contains no records.")

    required = {
        "policy", "frame_capacity", "repeat", "page_faults",
        "hit_ratio", "total_simulation_time_ms",
        "replacement_time_us", "peak_python_memory_kb",
    }
    missing = required - set(rows[0])
    if missing:
        raise ValueError(f"Missing CSV columns: {sorted(missing)}")

    return rows

def summarize(rows):
    groups = defaultdict(list)

    for row in rows:
        key = (int(row["frame_capacity"]), row["policy"])
        groups[key].append(row)

    summary = []
    for (frames, policy), items in sorted(groups.items()):
        record = {
            "frame_capacity": frames,
            "policy": policy,
            "runs": len(items),
        }

        for metric, _, _ in METRICS:
            values = [float(item[metric]) for item in items]
            record[f"mean_{metric}"] = mean(values)
            record[f"std_{metric}"] = (
                statistics.stdev(values) if len(values) > 1 else 0.0
            )

        summary.append(record)

    return summary

def save_summary(summary):
    fields = list(summary[0].keys())
    with SUMMARY_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(summary)

def save_charts(summary):
    policies = ["FIFO", "LRU", "LFU"]
    frames = sorted({row["frame_capacity"] for row in summary})

    for metric, title, ylabel in METRICS:
        fig, ax = plt.subplots(figsize=(8, 5))

        for policy in policies:
            points = [
                next(row for row in summary
                     if row["frame_capacity"] == frame
                     and row["policy"] == policy)
                for frame in frames
            ]

            values = [row[f"mean_{metric}"] for row in points]
            errors = [row[f"std_{metric}"] for row in points]

            ax.errorbar(
                frames, values, yerr=errors,
                marker="o", capsize=4, label=policy
            )

        ax.set_title(title)
        ax.set_xlabel("Frame capacity")
        ax.set_ylabel(ylabel)
        ax.set_xticks(frames)
        ax.grid(True, alpha=0.3)
        ax.legend()
        fig.tight_layout()

        chart_path = OUT / f"{metric}_comparison.png"
        fig.savefig(chart_path, dpi=160)
        plt.close(fig)
        print(f"Chart saved: {chart_path.name}")

def save_report(summary, source_rows):
    frames = sorted({row["frame_capacity"] for row in summary})
    policies = ["FIFO", "LRU", "LFU"]

    lines = [
        "# Page Replacement Benchmark Report",
        "",
        "## Experiment setup",
        "",
        f"- Raw benchmark records: {len(source_rows)}",
        f"- Frame capacities: {', '.join(map(str, frames))}",
        "- Algorithms: FIFO, LRU, LFU",
        "- Results are based on a synthetic page-reference trace.",
        "- Times are Python simulator measurements, not database latency.",
        "",
        "## Results",
        "",
        "| Frames | Algorithm | Avg. faults | Hit ratio | "
        "Total time (ms) | Replacement time (µs) | Peak traced memory (KB) |",
        "|---:|---|---:|---:|---:|---:|---:|",
    ]

    for row in summary:
        lines.append(
            f"| {row['frame_capacity']} | {row['policy']} "
            f"| {row['mean_page_faults']:.1f} "
            f"| {row['mean_hit_ratio']:.4f} "
            f"| {row['mean_total_simulation_time_ms']:.3f} "
            f"| {row['mean_replacement_time_us']:.3f} "
            f"| {row['mean_peak_python_memory_kb']:.2f} |"
        )

    lines += [
        "",
        "## Interpretation",
        "",
        "- Higher hit ratio and fewer page faults indicate better cache "
        "effectiveness for this trace.",
        "- Total simulation time measures the complete Python simulation.",
        "- Replacement time measures the victim-selection section instrumented "
        "by the simulator; it is not disk or database I/O latency.",
        "- Peak traced memory measures Python allocations tracked by "
        "`tracemalloc`, not total process RAM.",
        "- Timing results are environment-dependent. Use repeated runs and "
        "compare averages and standard deviations.",
        "- These are simulated page-replacement results, not direct measurements "
        "of PostgreSQL's internal buffer replacement policy.",
        "",
        "## Charts",
        "",
    ]

    for metric, title, _ in METRICS:
        lines.append(f"- **{title}:** `{metric}_comparison.png`")

    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    rows = load_results()
    summary = summarize(rows)

    save_summary(summary)
    save_charts(summary)
    save_report(summary, rows)

    print(f"\nSummary CSV: {SUMMARY_CSV}")
    print(f"Markdown report: {REPORT_MD}")
    print(f"Records summarized: {len(rows)}")

if __name__ == "__main__":
    main()
