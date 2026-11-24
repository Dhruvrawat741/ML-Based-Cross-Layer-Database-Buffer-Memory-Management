import joblib
from pathlib import Path

ROOT = Path(__file__).resolve().parent

source = ROOT / "models/ml_cache_policy_random_forest.joblib"
target = ROOT / "models/ml_cache_policy_random_forest_optimized.joblib"

model = joblib.load(source)
model.n_jobs = 1

joblib.dump(model, target)

print("Optimized model saved:", target)
print("Trees:", model.n_estimators)
print("n_jobs:", model.n_jobs)
