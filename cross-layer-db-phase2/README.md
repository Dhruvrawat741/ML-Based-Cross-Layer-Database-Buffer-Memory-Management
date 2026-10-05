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
