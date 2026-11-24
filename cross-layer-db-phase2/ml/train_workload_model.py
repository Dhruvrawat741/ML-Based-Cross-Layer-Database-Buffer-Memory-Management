from pathlib import Path
import json

import joblib
import numpy as np
import pandas as pd

from sklearn.ensemble import RandomForestClassifier
from sklearn.dummy import DummyClassifier
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    classification_report,
    confusion_matrix,
)

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "ml/features/cross_layer_dataset.csv"
MODEL_DIR = ROOT / "ml/models"
EVAL_DIR = ROOT / "ml/evaluation"

MODEL_DIR.mkdir(parents=True, exist_ok=True)
EVAL_DIR.mkdir(parents=True, exist_ok=True)

print("Loading unified dataset...")
df = pd.read_csv(DATA)

if "phase" not in df.columns:
    raise ValueError("Dataset must contain a 'phase' target column.")

time_col = next(
    (c for c in ["timestamp_utc", "timestamp", "time"] if c in df.columns),
    None,
)
if time_col is None:
    raise ValueError("No timestamp column found. Cannot perform chronological split.")

df[time_col] = pd.to_datetime(df[time_col], errors="coerce", utc=True)
df = df.dropna(subset=[time_col, "phase"]).sort_values(time_col).reset_index(drop=True)

# Remove timestamps, labels, and cumulative counters.
# Cumulative counters can reveal collection order instead of workload behaviour.
excluded = {"phase", time_col}
excluded.update(c for c in df.columns if c.endswith("_total"))

numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
features = [c for c in numeric_cols if c not in excluded]

if not features:
    raise ValueError("No numeric model features found.")

X = df[features].replace([np.inf, -np.inf], np.nan).fillna(0)
y = df["phase"].astype(str)

# Chronological split within each phase:
# first 80% for training, last 20% for testing.
# Leave a 30-second gap before the test segment to reduce near-boundary overlap.
train_indices = []
test_indices = []
gap_rows = []

for phase in sorted(y.unique()):
    phase_indices = df.index[y == phase].tolist()
    phase_indices.sort(key=lambda i: df.loc[i, time_col])

    split_at = int(len(phase_indices) * 0.8)
    phase_train = phase_indices[:split_at]
    phase_test = phase_indices[split_at:]

    if len(phase_train) < 20 or len(phase_test) < 5:
        raise ValueError(f"Not enough observations in phase '{phase}'.")

    # Exclude the final 30 seconds of training observations before testing.
    test_start_time = df.loc[phase_test[0], time_col]
    cutoff = test_start_time - pd.Timedelta(seconds=30)

    kept_train = [
        i for i in phase_train if df.loc[i, time_col] < cutoff
    ]
    removed = len(phase_train) - len(kept_train)

    if len(kept_train) < 20:
        raise ValueError(f"Too few training rows after applying gap for '{phase}'.")

    train_indices.extend(kept_train)
    test_indices.extend(phase_test)
    gap_rows.append({"phase": phase, "gap_rows_removed": removed})

train_indices.sort()
test_indices.sort()

X_train, X_test = X.loc[train_indices], X.loc[test_indices]
y_train, y_test = y.loc[train_indices], y.loc[test_indices]

print("\nFeatures used:")
for feature in features:
    print(" -", feature)

print("\nTraining distribution:")
print(y_train.value_counts().to_string())
print("\nTesting distribution:")
print(y_test.value_counts().to_string())
print(f"\nTraining rows: {len(X_train)}")
print(f"Testing rows: {len(X_test)}")

baseline = DummyClassifier(strategy="most_frequent")
baseline.fit(X_train, y_train)
baseline_pred = baseline.predict(X_test)

model = RandomForestClassifier(
    n_estimators=300,
    max_depth=14,
    min_samples_leaf=3,
    class_weight="balanced_subsample",
    random_state=42,
    n_jobs=-1,
)
print("\nTraining Random Forest...")
model.fit(X_train, y_train)
pred = model.predict(X_test)

labels = sorted(y.unique())
accuracy = accuracy_score(y_test, pred)
macro_f1 = f1_score(y_test, pred, average="macro")

print("\n========== CHRONOLOGICAL VALIDATION RESULTS ==========")
print(f"Baseline accuracy: {accuracy_score(y_test, baseline_pred):.4f}")
print(f"Random Forest accuracy: {accuracy:.4f}")
print(f"Random Forest macro F1: {macro_f1:.4f}")
print("\nClassification report:")
print(classification_report(y_test, pred, labels=labels, zero_division=0))
print("Confusion matrix:")
print(confusion_matrix(y_test, pred, labels=labels))
print("Class order:", labels)

model_path = MODEL_DIR / "workload_state_random_forest_chronological.joblib"
joblib.dump(
    {"model": model, "features": features, "classes": labels},
    model_path,
)

importance = pd.DataFrame({
    "feature": features,
    "importance": model.feature_importances_,
}).sort_values("importance", ascending=False)

importance.to_csv(EVAL_DIR / "chronological_feature_importance.csv", index=False)

report = {
    "validation": "chronological_within_each_phase",
    "gap_seconds": 30,
    "training_rows": len(X_train),
    "testing_rows": len(X_test),
    "features": features,
    "excluded_cumulative_counters": sorted(
        c for c in df.columns if c.endswith("_total")
    ),
    "training_distribution": y_train.value_counts().to_dict(),
    "testing_distribution": y_test.value_counts().to_dict(),
    "gap_rows_removed": gap_rows,
    "baseline_accuracy": accuracy_score(y_test, baseline_pred),
    "random_forest_accuracy": accuracy,
    "random_forest_macro_f1": macro_f1,
    "class_order": labels,
    "confusion_matrix": confusion_matrix(y_test, pred, labels=labels).tolist(),
    "classification_report": classification_report(
        y_test, pred, labels=labels, output_dict=True, zero_division=0
    ),
    "feature_importance": importance.to_dict(orient="records"),
    "interpretation": (
        "Classifies the recorded workload phase from contemporaneous OS and "
        "query-level metrics. It does not predict page reuse or future page accesses."
    ),
}

with open(EVAL_DIR / "chronological_model_report.json", "w") as f:
    json.dump(report, f, indent=2, default=str)

print("\nTop features:")
print(importance.head(10).to_string(index=False))
print(f"\nModel saved: {model_path}")
print(f"Report saved: {EVAL_DIR / 'chronological_model_report.json'}")
print(f"Feature importance saved: {EVAL_DIR / 'chronological_feature_importance.csv'}")
