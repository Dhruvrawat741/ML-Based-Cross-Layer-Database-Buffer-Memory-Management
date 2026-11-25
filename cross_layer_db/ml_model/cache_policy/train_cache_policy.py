import csv
import json
import random
from collections import defaultdict
from itertools import groupby
from pathlib import Path

import joblib
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, roc_auc_score
from sklearn.metrics import confusion_matrix

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
MODELS = ROOT / "models"
RESULTS = ROOT / "results"

SNAPSHOT_FILE = DATA / "olist_page_snapshots_pressure.csv"
QUERY_FILE = DATA / "olist_2000_records.csv"
TRAINING_FILE = DATA / "cache_policy_training_data.csv"
MODEL_FILE = MODELS / "ml_cache_policy_random_forest.joblib"

TRAIN_RATIO = 0.80
POSITIVE_SAMPLE_RATE = 0.05
RANDOM_SEED = 42

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

for folder in (DATA, MODELS, RESULTS):
    folder.mkdir(parents=True, exist_ok=True)


def load_query_metrics():
    metrics = {}

    with QUERY_FILE.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            metrics[int(row["record_id"])] = {
                "query_number": int(row["query_number"]),
                "execution_time_ms": float(row["execution_time_ms"]),
                "shared_hit_blocks": int(row["shared_hit_blocks"]),
                "shared_read_blocks": int(row["shared_read_blocks"]),
            }

    return metrics


def generate_dataset():
    if not SNAPSHOT_FILE.exists():
        raise FileNotFoundError(SNAPSHOT_FILE)

    query_metrics = load_query_metrics()
    rng = random.Random(RANDOM_SEED)

    history = {}
    total = 0
    kept = 0
    positive = 0
    negative = 0

    with SNAPSHOT_FILE.open(newline="", encoding="utf-8") as source:
        reader = csv.DictReader(source)
        groups = iter(groupby(
            reader,
            key=lambda row: int(row["snapshot_id"])
        ))

        try:
            current_id, current_iter = next(groups)
            current_rows = list(current_iter)
            next_id, next_iter = next(groups)
            next_rows = list(next_iter)
        except StopIteration:
            raise ValueError("Need at least two snapshots.")

        with TRAINING_FILE.open("w", newline="", encoding="utf-8") as output:
            fields = ["snapshot_id", "page_id"] + FEATURES + ["will_remain_resident"]
            writer = csv.DictWriter(output, fieldnames=fields)
            writer.writeheader()

            while True:
                next_pages = {row["page_id"] for row in next_rows}
                query = query_metrics.get(current_id)

                if query is None:
                    raise ValueError(
                        f"No query metrics for snapshot {current_id}"
                    )

                for row in current_rows:
                    total += 1
                    page = row["page_id"]

                    previous = history.get(page)

                    if previous is None:
                        recency = current_id + 1
                        first_seen = current_id
                        frequency = 0
                    else:
                        last_seen, first_seen, frequency = previous
                        recency = current_id - last_seen

                    label = int(page in next_pages)

                    # Keep all eviction examples and sample
                    # page-persistence examples.
                    if label == 1 and rng.random() > POSITIVE_SAMPLE_RATE:
                        history[page] = (
                            current_id,
                            first_seen,
                            frequency + 1
                        )
                        continue

                    record = {
                        "snapshot_id": current_id,
                        "page_id": page,
                        "recency_snapshots": recency,
                        "observed_frequency": frequency,
                        "page_age_snapshots": current_id - first_seen,
                        "usage_count": int(row["usage_count"]),
                        "is_dirty": int(str(row["dirty"]).lower() == "true"),
                        "pin_count": int(row["pinned"]),
                        **query,
                        "will_remain_resident": label,
                    }

                    writer.writerow(record)
                    kept += 1

                    if label:
                        positive += 1
                    else:
                        negative += 1

                    history[page] = (
                        current_id,
                        first_seen,
                        frequency + 1
                    )

                if current_id % 200 == 0:
                    print(
                        f"Processed snapshot {current_id}; "
                        f"kept {kept:,} examples",
                        flush=True
                    )

                try:
                    current_id, current_rows = next_id, next_rows
                    next_id, next_iter = next(groups)
                    next_rows = list(next_iter)
                except StopIteration:
                    break

    print("\nDataset generation complete.")
    print("Original observations:", f"{total:,}")
    print("Training examples:", f"{kept:,}")
    print("Positive labels:", f"{positive:,}")
    print("Eviction labels:", f"{negative:,}")
    print("Dataset:", TRAINING_FILE)


def train_model():
    df = pd.read_csv(TRAINING_FILE)

    snapshot_ids = sorted(df["snapshot_id"].unique())
    cutoff = snapshot_ids[int(len(snapshot_ids) * TRAIN_RATIO)]

    train = df[df["snapshot_id"] < cutoff]
    test = df[df["snapshot_id"] >= cutoff]

    X_train = train[FEATURES]
    y_train = train["will_remain_resident"]

    X_test = test[FEATURES]
    y_test = test["will_remain_resident"]

    if y_train.nunique() < 2 or y_test.nunique() < 2:
        raise ValueError("Insufficient class diversity in chronological split.")

    print("\nTraining Random Forest...")
    model = RandomForestClassifier(
        n_estimators=150,
        max_depth=12,
        min_samples_leaf=5,
        class_weight="balanced",
        random_state=RANDOM_SEED,
        n_jobs=-1,
    )

    model.fit(X_train, y_train)

    predictions = model.predict(X_test)
    probabilities = model.predict_proba(X_test)[:, 1]

    report = classification_report(
        y_test,
        predictions,
        zero_division=0,
        output_dict=True
    )

    auc = roc_auc_score(y_test, probabilities)

    joblib.dump(model, MODEL_FILE)

    metadata = {
        "model": "RandomForestClassifier",
        "target": "will_remain_resident",
        "target_definition": (
            "Page is present in the immediately following buffer snapshot."
        ),
        "features": FEATURES,
        "training_examples": len(train),
        "testing_examples": len(test),
        "chronological_cutoff": int(cutoff),
        "roc_auc": float(auc),
        "classification_report": report,
        "confusion_matrix": confusion_matrix(
            y_test, predictions
        ).tolist(),
        "note": (
            "Predicts observed residency persistence, not exact logical "
            "page reuse or PostgreSQL's internal eviction decisions."
        )
    }

    (RESULTS / "model_evaluation.json").write_text(
        json.dumps(metadata, indent=4)
    )

    print("\n========== MODEL EVALUATION ==========")
    print(classification_report(y_test, predictions, zero_division=0))
    print("ROC AUC:", round(auc, 4))
    print("Confusion matrix:")
    print(confusion_matrix(y_test, predictions))
    print("\nModel saved:", MODEL_FILE)
    print("Evaluation saved:", RESULTS / "model_evaluation.json")


if __name__ == "__main__":
    generate_dataset()
    train_model()
