# ML-Based Cross-Layer Database Buffer & Memory Management

An experimental project exploring operating-system monitoring, database workload measurements, page-replacement policies, and machine-learning-assisted cache decisions. It includes a Streamlit dashboard connected to PostgreSQL, a four-policy cache simulator, and supporting data-collection and model-evaluation scripts.

> **Measurement note:** Dashboard cache hit ratios and page faults are simulator results for the generated workload or an uploaded ordered page-reference trace. They are not PostgreSQL's own shared-buffer hit ratios. PostgreSQL query measurements and buffer counters are collected separately.

## Features

### Interactive dashboard

The Streamlit application is in `cross_layer_db/dashboard/app.py` and provides:

- **Overview & Benchmark:** run FIFO, LRU, LFU, and ML against the same trace and cache capacity; compare hits, faults, evictions, timing, and Python memory.
- **SQL Query Lab:** execute one SQL statement at a time against `olist_db`. Supported statement types are `SELECT`, `INSERT`, `UPDATE`, `DELETE`, and `CALL`. Data-changing statements require confirmation. DDL and multi-statement input are blocked.
- **Experiment History:** view policy metrics persisted in PostgreSQL.
- CSV and JSON downloads for benchmark results.

The built-in workload generator creates a repeatable synthetic mixed-locality trace. You can also upload a CSV containing an ordered `page_id` column. A generated trace must not be described as a captured PostgreSQL page-reference trace.

### PostgreSQL integration

Dashboard experiments are saved in the `cachelab` schema, using these tables:

- `cachelab.workloads`
- `cachelab.policies`
- `cachelab.experiments`
- `cachelab.experiment_metrics`

The project database also includes workload catalog and audit objects, including `workload_catalog_view`, `workload_audit_trigger`, `get_workload_count()`, `log_workload_changes()`, `update_workload_description()`, and `policy_comparison_view`.

New dashboard runs use the workload name **Workload**. Existing database rows are not renamed automatically.

### ML cache-policy component

The active ML model is in `cross_layer_db/ml_model/cache_policy/`. It predicts page-residency probability from snapshot-derived page features and ranks eviction candidates. The same component is used by the four-policy snapshot evaluation.

## Technology stack

- Python 3
- Streamlit, pandas, NumPy, Plotly
- scikit-learn
- PostgreSQL and psycopg 3
- sqlparse
- psutil
- Git / GitHub

## Project setup

### 1. Clone and enter the project

```bash
git clone https://github.com/Dhruvrawat741/ML-Based-Cross-Layer-Database-Buffer-Memory-Management.git
cd ML-Based-Cross-Layer-Database-Buffer-Memory-Management/cross_layer_db
```

### 2. Create and activate a virtual environment

**Ubuntu / macOS**

```bash
python3 -m venv venv
source venv/bin/activate
```

**Windows PowerShell**

```powershell
py -3 -m venv venv
.\venv\Scripts\Activate.ps1
```

If PowerShell blocks activation, run this for the current PowerShell process and activate again:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\venv\Scripts\Activate.ps1
```

### 3. Install dashboard dependencies

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 4. Configure PostgreSQL

Ensure PostgreSQL is running and that the `olist_db` database contains the `cachelab` schema and the four tables listed above. Create a login role and grant it access (run as a PostgreSQL administrator; choose your own password):

```sql
CREATE ROLE cachelab_app LOGIN PASSWORD 'CHOOSE_A_PASSWORD';
GRANT USAGE ON SCHEMA cachelab TO cachelab_app;
GRANT SELECT, INSERT, UPDATE, DELETE
ON ALL TABLES IN SCHEMA cachelab TO cachelab_app;
GRANT USAGE, SELECT
ON ALL SEQUENCES IN SCHEMA cachelab TO cachelab_app;
```

Run `CREATE ROLE` only once. If the role already exists, do not create it again. The schema and tables must be created before launching the dashboard; the application does not initialize the database schema.

Set the connection variables in the same terminal where Streamlit will run.

**Ubuntu / macOS**

```bash
export DB_HOST=127.0.0.1
export DB_PORT=5432
export DB_NAME=olist_db
export DB_USER=cachelab_app
export DB_PASSWORD='YOUR_CHOSEN_PASSWORD'
```

**Windows PowerShell**

```powershell
$env:DB_HOST = "127.0.0.1"
$env:DB_PORT = "5432"
$env:DB_NAME = "olist_db"
$env:DB_USER = "cachelab_app"
$env:DB_PASSWORD = "YOUR_CHOSEN_PASSWORD"
```

Using `127.0.0.1` forces a TCP connection, which allows PostgreSQL password authentication rather than local Unix-socket peer authentication. Keep credentials out of source control.

### 5. Launch the dashboard

From the `cross_layer_db` directory, with the virtual environment active and database variables set:

```bash
python -m streamlit run dashboard/app.py
```

Open [http://localhost:8501](http://localhost:8501).

## Using the dashboard

1. Open **Overview & Benchmark**.
2. Configure reference count, page universe, cache capacity, locality, scan share, and random seed, or upload an ordered `page_id` CSV.
3. Run all four policies. Each policy receives the same input trace and capacity.
4. Review the comparison metrics and charts. Download CSV/JSON if needed.
5. Open **SQL Query Lab** to enter a single SQL statement. Confirm before executing `INSERT`, `UPDATE`, `DELETE`, or `CALL`.
6. Open **Experiment History** to inspect saved policy metrics.

A dashboard run stores one experiment and four policy metric rows in PostgreSQL. Its workload name is `Workload`.

## Useful SQL examples

Run these from the SQL Query Lab or from `psql`:

```sql
-- Compare policies from saved experiments
SELECT *
FROM cachelab.policy_comparison_view
ORDER BY experiment_id DESC, policy_name;

-- Count registered workloads
SELECT cachelab.get_workload_count();

-- Inspect workload catalog
SELECT * FROM cachelab.workload_catalog_view;

-- Inspect recent audit events
SELECT * FROM cachelab.audit_logs ORDER BY 1 DESC LIMIT 20;
```

The SQL Query Lab intentionally does not allow schema-changing commands such as `CREATE`, `ALTER`, or `DROP`, transaction-control statements, or multiple statements in one submission.

## Repository structure

```text
cross_layer_db/
├── dashboard/
│   └── app.py
├── experiments/
│   ├── olist_workload.sql
│   ├── measure_query_metrics.py
│   └── compare_os_data.py
├── os_monitor/
│   └── monitor.py
├── ml_model/
│   └── cache_policy/
│       ├── data/
│       ├── models/
│       ├── ml_policy.py
│       ├── train_cache_policy.py
│       └── supporting scripts
├── page_replacement_benchmark/
│   ├── algorithms.py
│   ├── evaluate_snapshot_evictions.py
│   ├── fifo.py
│   ├── lfu.py
│   ├── lru.py
│   ├── ml_policy.py
│   └── results/
├── data/
│   ├── database/
│   ├── raw/
│   └── OS_result/
├── scripts/
│   └── monitoring/
└── requirements.txt
```

## Methodology and limitations

- FIFO, LRU, LFU, and ML are compared in the dashboard simulator using an identical ordered trace and cache capacity.
- The dashboard's generated trace is synthetic. Uploaded traces are only as representative as the data supplied.
- PostgreSQL `EXPLAIN (ANALYZE, BUFFERS)` gives query-level timing and buffer counters; it does not provide the complete chronological logical page-reference stream needed to reproduce the database buffer cache exactly.
- `pg_buffercache` snapshots show resident buffers at sampling time, not the full sequence of page accesses.
- The ML cache-policy model uses snapshot-derived features to rank eviction candidates; its evaluation is not a logical page-reference trace or a cache hit-rate simulation.
- ML training and inference overhead should be considered separately from cache hit ratio.
- Python memory measurements are not PostgreSQL server memory measurements.
- Results depend on workload, cache capacity, implementation, and machine. Do not present simulator results as production PostgreSQL performance.

## Troubleshooting

### `python` is not found on Ubuntu

Use `python3` to create the environment, activate it, and then use `python` inside the activated environment.

### `externally-managed-environment`

Install packages inside the virtual environment. Do not use `--break-system-packages`.

### PostgreSQL peer authentication failed

Set `DB_HOST=127.0.0.1` in the same terminal before launching Streamlit. Check that the role password is correct and that PostgreSQL accepts password authentication over TCP.

### Experiment History cannot connect

Verify PostgreSQL is running, confirm the `DB_*` variables are set in the Streamlit terminal, and confirm that `cachelab_app` has SELECT access to the required tables.

### SQL Query Lab reports a permission error

The dashboard role needs the appropriate table and sequence privileges. Grant only the privileges needed for the operations you intend to demonstrate.

---

Keep generated and measured results clearly distinguished. Reproducible experiments and honest interpretation are essential to evaluating this project.
