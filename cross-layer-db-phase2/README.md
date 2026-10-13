# ML-Based Cross-Layer Database Buffer & Memory Management

## Phase 2 — OS Data Collection

Current work focuses on OS-level data collection. ML is intentionally not implemented yet.

### Collected metrics
- Timestamp
- CPU utilization
- RAM utilization
- Available RAM
- Disk read activity
- Disk write activity

Data is saved to `data/raw/os_metrics.csv`.

### Architecture

```text
Ubuntu Linux
    ↓
  psutil
    ↓
OS Monitoring Script
    ↓
CPU / RAM / Disk I/O
    ↓
os_metrics.csv
    ↓
Future: DBMS data
    ↓
Future: Combined OS + DBMS dataset
    ↓
Phase 3: ML
```

### Environment
- Ubuntu 26.04.1 LTS
- ARM64 / aarch64
- Python 3
- Git
- psutil
- pandas

### Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Run

From the project root:

```bash
python os_monitor/monitor.py
```

Stop with `Ctrl+C`.

### Verify syntax

```bash
python -m py_compile os_monitor/monitor.py
```

### Completed
- Ubuntu Linux VM configured
- ARM64 environment configured
- Python virtual environment created
- Git configured
- psutil and pandas installed
- OS monitoring script implemented
- OS metrics collected into CSV

### Next
- PostgreSQL/DBMS monitoring
- DB workload generation
- Combined OS + DBMS dataset
- Feature engineering
- ML model training in Phase 3


## PostgreSQL and ML Prototype — Phase 2

### Completed work
- Installed and configured PostgreSQL 18.6 on Ubuntu ARM64.
- Created the `cross_layer_db` benchmark database.
- Initialized pgbench tables with 200,000 account records.
- Executed a pgbench workload of 400 transactions with zero failures.
- Generated a synthetic page-access dataset containing 10,000 records.
- Trained an initial Random Forest classifier.

### ML artifacts
- `ml/generate_dataset.py` — generates the synthetic access trace.
- `ml/train.py` — trains and evaluates the Random Forest.
- `data/processed/page_access_dataset.csv` — generated training dataset.

### Current limitations
The page-access trace is synthetic, not a real PostgreSQL page-level trace.
The initial model is a prototype; improvements and comparisons against
traditional replacement policies remain future work.
