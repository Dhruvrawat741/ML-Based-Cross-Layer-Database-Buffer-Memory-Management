from pathlib import Path
import json

import joblib
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]

MODEL_PATH = (
    ROOT / "ml/models/workload_state_random_forest_chronological.joblib"
)
DATA_PATH = ROOT / "ml/features/cross_layer_dataset.csv"
REPORT_PATH = ROOT / "ml/evaluation/buffer_advisor_report.json"

if not MODEL_PATH.exists():
    raise FileNotFoundError(f"Model not found: {MODEL_PATH}")

if not DATA_PATH.exists():
    raise FileNotFoundError(f"Dataset not found: {DATA_PATH}")

artifact = joblib.load(MODEL_PATH)
model = artifact["model"]
features = artifact["features"]

df = pd.read_csv(DATA_PATH)

if df.empty:
    raise ValueError("Dataset is empty.")

# Use the latest recorded observation for this demonstration.
if "timestamp_utc" in df.columns:
    df["timestamp_utc"] = pd.to_datetime(
        df["timestamp_utc"], errors="coerce", utc=True
    )
    df = df.dropna(subset=["timestamp_utc"]).sort_values("timestamp_utc")

latest = df.iloc[[-1]].copy()

missing = [f for f in features if f not in latest.columns]
if missing:
    raise ValueError(f"Missing model features: {missing}")

X = latest[features].apply(pd.to_numeric, errors="coerce").fillna(0)

prediction = model.predict(X)[0]
probabilities = model.predict_proba(X)[0]
class_probabilities = dict(zip(model.classes_, probabilities))

recommendations = {
    "idle": {
        "priority": "Low",
        "action": (
            "Maintain the current buffer configuration. "
            "Use idle periods for planned maintenance and diagnostics."
        ),
        "monitor": (
            "Watch memory availability and background disk activity."
        ),
    },
    "light": {
        "priority": "Normal",
        "action": (
            "Keep the current configuration. Monitor cache behaviour "
            "and avoid unnecessary buffer configuration changes."
        ),
        "monitor": (
            "Track shared reads, shared hits, and disk I/O trends."
        ),
    },
    "heavy": {
        "priority": "High",
        "action": (
            "Investigate memory pressure and possible buffer churn. "
            "Review shared reads, temporary I/O, and query plans before "
            "considering any configuration adjustment."
        ),
        "monitor": (
            "Monitor RAM availability, swap, shared reads, temporary "
            "writes, and query execution times."
        ),
    },
}

advice = recommendations[prediction]

result = {
    "timestamp_utc": str(latest.iloc[0].get("timestamp_utc", "unknown")),
    "predicted_workload": prediction,
    "confidence": round(float(max(probabilities)), 4),
    "class_probabilities": {
        k: round(float(v), 4)
        for k, v in class_probabilities.items()
    },
    "priority": advice["priority"],
    "recommended_action": advice["action"],
    "metrics_to_monitor": advice["monitor"],
    "model_scope": (
        "Workload-state classification from OS and query-level metrics. "
        "Not a page-reuse predictor or an automatic PostgreSQL buffer controller."
    ),
}

print("\n========== BUFFER MANAGEMENT ADVISOR ==========")
print("Observation:", result["timestamp_utc"])
print("Predicted workload:", prediction.upper())
print("Confidence:", f"{result['confidence']:.2%}")
print("\nClass probabilities:")
for name, probability in result["class_probabilities"].items():
    print(f"  {name}: {probability:.2%}")

print("\nRecommended priority:", advice["priority"])
print("Recommended action:", advice["action"])
print("Monitor:", advice["monitor"])

REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
REPORT_PATH.write_text(json.dumps(result, indent=2))

print("\nReport saved:", REPORT_PATH)
print("\nNote: This is advisory only. No PostgreSQL settings were changed.")
