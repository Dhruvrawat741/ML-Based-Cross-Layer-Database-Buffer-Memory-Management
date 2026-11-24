import csv
import statistics
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"

INPUT = RESULTS / "four_policy_eviction_results.csv"
POLICIES = ["FIFO", "LRU", "LFU", "ML"]

METRICS = [
    ("precision_at_k", "Precision@K", "Mean Precision@K"),
    ("recall_at_k", "Recall@K", "Mean Recall@K"),
    ("f1_at_k", "F1@K", "Mean F1@K"),
    ("decision_latency_us", "Decision Latency", "Latency (µs)"),
]


def load_results():
    if not INPUT.exists():
        raise FileNotFoundError(
            f"{INPUT} not found. Run evaluate_snapshot_evictions.py first."
        )

    with INPUT.open(newline="", encoding="utf-8") as file:
        rows = list(csv.DictReader(file))

    if not rows:
        raise ValueError("The comparison results CSV is empty.")

    return rows


def calculate_statistics(rows):
    grouped = defaultdict(list)

    for row in rows:
        grouped[row["policy"]].append(row)

    missing = set(POLICIES) - set(grouped)
    if missing:
        raise ValueError(f"Missing policy results: {sorted(missing)}")

    summary = {}

    for policy in POLICIES:
        summary[policy] = {}

        for metric, _, _ in METRICS:
            values = [
                float(row[metric])
                for row in grouped[policy]
            ]

            summary[policy][metric] = {
                "mean": statistics.mean(values),
                "std": statistics.stdev(values) if len(values) > 1 else 0,
            }

    return summary


def plot_ranking_metrics(summary):
    metrics = METRICS[:3]
    x = list(range(len(metrics)))
    width = 0.18

    fig, ax = plt.subplots(figsize=(10, 6))

    for index, policy in enumerate(POLICIES):
        means = [
            summary[policy][metric[0]]["mean"]
            for metric in metrics
        ]
        errors = [
            summary[policy][metric[0]]["std"]
            for metric in metrics
        ]

        positions = [
            value + (index - 1.5) * width
            for value in x
        ]

        ax.bar(
            positions,
            means,
            width,
            yerr=errors,
            capsize=3,
            label=policy,
        )

    ax.set_title("Four-Policy Eviction Ranking Comparison")
    ax.set_ylabel("Score")
    ax.set_xticks(x)
    ax.set_xticklabels([metric[1] for metric in metrics])
    ax.set_ylim(bottom=0)
    ax.grid(axis="y", alpha=0.3)
    ax.legend()

    fig.tight_layout()
    path = RESULTS / "four_policy_ranking_comparison.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)

    print(f"Saved: {path}")


def plot_latency(summary):
    means = [
        summary[policy]["decision_latency_us"]["mean"]
        for policy in POLICIES
    ]
    errors = [
        summary[policy]["decision_latency_us"]["std"]
        for policy in POLICIES
    ]

    fig, ax = plt.subplots(figsize=(8, 5))

    ax.bar(
        POLICIES,
        means,
        yerr=errors,
        capsize=4,
    )

    ax.set_title("Four-Policy Decision Latency Comparison")
    ax.set_ylabel("Decision latency (µs)")
    ax.grid(axis="y", alpha=0.3)

    fig.tight_layout()
    path = RESULTS / "four_policy_latency_comparison.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)

    print(f"Saved: {path}")


def main():
    rows = load_results()
    summary = calculate_statistics(rows)

    plot_ranking_metrics(summary)
    plot_latency(summary)

    print("\n========== FOUR-POLICY SUMMARY ==========")

    for policy in POLICIES:
        print(f"\n{policy}")

        for metric, title, _ in METRICS:
            values = summary[policy][metric]
            print(
                f"  {title}: {values['mean']:.4f} "
                f"(std: {values['std']:.4f})"
            )


if __name__ == "__main__":
    main()
