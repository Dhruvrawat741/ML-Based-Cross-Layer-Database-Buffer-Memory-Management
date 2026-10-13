
import pandas as pd
from pathlib import Path
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    confusion_matrix,
    classification_report,
)
from sklearn.dummy import DummyClassifier
import joblib

DATA_PATH = Path("data/processed/page_access_dataset.csv")
MODEL_PATH = Path("ml/random_forest_model.joblib")

df = pd.read_csv(DATA_PATH)

features = [
    "page_id",
    "previous_accesses",
    "recency",
    "recent_frequency",
]
target = "label_accessed_soon"

# Chronological split: earlier records train; later records test.
split = int(len(df) * 0.80)
X_train = df[features].iloc[:split]
y_train = df[target].iloc[:split]
X_test = df[features].iloc[split:]
y_test = df[target].iloc[split:]

model = RandomForestClassifier(
    n_estimators=100,
    max_depth=12,
    min_samples_leaf=5,
    class_weight="balanced",
    random_state=42,
    n_jobs=-1,
)

model.fit(X_train, y_train)
predictions = model.predict(X_test)

# Baseline: always predict the majority class from training data.
baseline = DummyClassifier(strategy="most_frequent")
baseline.fit(X_train, y_train)
baseline_predictions = baseline.predict(X_test)

print("\n=== Random Forest Results ===")
print(f"Test records: {len(y_test)}")
print(f"Accuracy:  {accuracy_score(y_test, predictions):.4f}")
print(f"Precision: {precision_score(y_test, predictions, zero_division=0):.4f}")
print(f"Recall:    {recall_score(y_test, predictions, zero_division=0):.4f}")
print(f"F1-score:  {f1_score(y_test, predictions, zero_division=0):.4f}")
print("\nConfusion matrix:")
print(confusion_matrix(y_test, predictions))
print("\nClassification report:")
print(classification_report(y_test, predictions, zero_division=0))

print("\n=== Majority-Class Baseline ===")
print(f"Accuracy: {accuracy_score(y_test, baseline_predictions):.4f}")
print(f"F1-score: {f1_score(y_test, baseline_predictions, zero_division=0):.4f}")

MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
joblib.dump(model, MODEL_PATH)
print(f"\nModel saved to: {MODEL_PATH}")

print("\nFeature importance:")
for name, importance in sorted(
    zip(features, model.feature_importances_),
    key=lambda item: item[1],
    reverse=True,
):
    print(f"{name}: {importance:.4f}")
