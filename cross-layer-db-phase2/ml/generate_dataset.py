
import csv
import random
from collections import deque
from pathlib import Path

random.seed(42)

OUTPUT = Path("data/processed/page_access_dataset.csv")
OUTPUT.parent.mkdir(parents=True, exist_ok=True)

NUM_PAGES = 200
NUM_ACCESSES = 10000
FUTURE_WINDOW = 10

# Simulated database page-access trace.
# Some pages are frequently accessed; others are occasional.
hot_pages = list(range(20))
warm_pages = list(range(20, 80))
cold_pages = list(range(80, NUM_PAGES))

trace = []

for _ in range(NUM_ACCESSES):
    r = random.random()

    if r < 0.60:
        page = random.choice(hot_pages)
    elif r < 0.90:
        page = random.choice(warm_pages)
    else:
        page = random.choice(cold_pages)

    trace.append(page)

# Create features using only accesses observed up to each position.
rows = []
recent = deque(maxlen=50)
last_seen = {}
access_count = {}
window_counts = {}

for i, page in enumerate(trace):
    # Label: will this page appear in the next 10 accesses?
    future = trace[i + 1:i + 1 + FUTURE_WINDOW]
    label = int(page in future)

    previous_accesses = access_count.get(page, 0)
    recency = i - last_seen[page] if page in last_seen else i + 1
    recent_frequency = sum(1 for p in recent if p == page)

    rows.append({
        "position": i,
        "page_id": page,
        "previous_accesses": previous_accesses,
        "recency": recency,
        "recent_frequency": recent_frequency,
        "label_accessed_soon": label,
    })

    access_count[page] = previous_accesses + 1
    last_seen[page] = i
    recent.append(page)

with OUTPUT.open("w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)

print(f"Dataset saved to: {OUTPUT}")
print(f"Rows: {len(rows)}")
print(f"Positive labels: {sum(r['label_accessed_soon'] for r in rows)}")
print(f"Negative labels: {len(rows) - sum(r['label_accessed_soon'] for r in rows)}")
