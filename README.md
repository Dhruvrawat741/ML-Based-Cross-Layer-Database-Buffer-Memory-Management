
# ML-Based Cross-Layer Database Buffer & Memory Management

An experimental project exploring how operating-system metrics, database workload information, page-access patterns, and machine learning can support better database buffer-management decisions.

> **Current status:** OS monitoring, PostgreSQL workload experiments, synthetic page-access prediction, and FIFO/LRU/LFU simulation are implemented. Integrating ML predictions into a replacement policy and validating the approach against real PostgreSQL buffer-page traces remain future work.

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Current Implementation](#2-current-implementation)
3. [Technology Stack](#3-technology-stack)
4. [Environment Setup](#4-environment-setup)
5. [PostgreSQL Configuration](#5-postgresql-configuration)
6. [OS Monitoring](#6-os-monitoring)
7. [Database Workload Experiments](#7-database-workload-experiments)
8. [Synthetic Dataset Generation](#8-synthetic-dataset-generation)
9. [Machine Learning Model](#9-machine-learning-model)
10. [Page Replacement Simulation](#10-page-replacement-simulation)
11. [Benchmark Report Generation](#11-benchmark-report-generation)
12. [Complete Experiment Workflow](#12-complete-experiment-workflow)
13. [Results and Evaluation Metrics](#13-results-and-evaluation-metrics)
14. [Project Structure](#14-project-structure)
15. [Limitations and Future Work](#15-limitations-and-future-work)
16. [Troubleshooting](#16-troubleshooting)

## 1. Project Overview

Database buffer managers and operating-system memory managers make decisions at different layers. Their decisions can affect memory utilization, disk I/O, page faults, and query execution time.

This project investigates whether combining database workload information with operating-system metrics and ML-based page-access predictions can improve memory-management decisions.

### Proposed architecture

```text
              PostgreSQL Workloads
                       |
                       v
              Query Execution Data
                       |
                       v
                DBMS Metrics
                       |
                       |
Ubuntu Linux            |
     |                  |
     v                  |
CPU / RAM / Disk I/O    |
     |                  |
     +--------+---------+
              |
              v
       Data Collection
              |
              v
      Feature Engineering
              |
              v
       ML Page Predictor
              |
              v
    Adaptive Replacement Policy
              |
              v
    FIFO / LRU / LFU Comparison
              |
              v
       Performance Evaluation
```

The complete cross-layer architecture is the target design. The current implementation consists of separate collection scripts, a synthetic ML prototype, and a page-replacement simulator.

## 2. Current Implementation

| Component | Current status |
|---|---|
| Ubuntu ARM64 development environment | Configured |
| Python virtual environment | Configured |
| PostgreSQL installation | Configured |
| PostgreSQL Olist database and read-only workload | Prepared |
| OS CPU, memory, and disk-I/O monitoring | Implemented |
| PostgreSQL query measurement | Implemented |
| Synthetic page-access dataset | Generated |
| Random Forest future-access prediction | Prototype implemented |
| FIFO page-replacement simulation | Implemented |
| LRU page-replacement simulation | Implemented |
| LFU page-replacement simulation | Implemented |
| Repeated benchmark experiments | Implemented |
| Benchmark summary and charts | Report generator prepared; run to produce the outputs |
| ML-guided victim selection | Not yet integrated |
| Real PostgreSQL buffer-manager integration | Future work |

## 3. Technology Stack

- **Operating system:** Ubuntu Linux ARM64, running in a UTM virtual machine on a Mac.
- **Database:** PostgreSQL 18.6.
- **Language:** Python 3.
- **Monitoring:** `psutil`.
- **Data processing:** `pandas`.
- **Machine learning:** scikit-learn Random Forest.
- **Database connectivity:** psycopg 3.
- **Benchmarking:** Python-based page-replacement simulator.
- **Development:** VS Code Remote SSH, Git, and GitHub.

## 4. Environment Setup

### 4.1 Open the project

The project is located inside the Ubuntu VM.

```bash
cd ~/github-project/cross-layer-db-phase2
```

Open it in VS Code from the VM terminal:

```bash
code .
```

### 4.2 Activate the Python virtual environment

The existing virtual environment is located at `~/cross-layer-db/venv`.

```bash
source ~/cross-layer-db/venv/bin/activate
```

Verify Python:

```bash
python --version
```

### 4.3 Install dependencies

Install the dependencies listed in the repository:

```bash
python -m pip install -r requirements.txt
```

Install the additional packages used by the ML, database-measurement, and reporting scripts:

```bash
python -m pip install scikit-learn joblib "psycopg[binary]" matplotlib
```

Verify the main imports:

```bash
python -c "import psutil, pandas, sklearn, joblib, psycopg, matplotlib; print('Dependencies OK')"
```

If a package is missing, install it inside the activated virtual environment rather than the system Python environment.

## 5. PostgreSQL Configuration

PostgreSQL 18.6 is installed in the Ubuntu VM. The experiments use the `olist_db` database and the `experiment_user` database role.

### 5.1 Check PostgreSQL

```bash
sudo systemctl status postgresql
```

If the service is stopped:

```bash
sudo systemctl start postgresql
```

Check the installed client version:

```bash
psql --version
```

### 5.2 Connect to the database

```bash
psql -h localhost -U experiment_user -d olist_db
```

Enter the password when prompted.

To check the database tables:

```sql
\dt
```

Exit the PostgreSQL shell:

```sql
\q
```

### 5.3 Configure credentials for scripts

For scripts that read the `PGPASSWORD` environment variable, set it in the terminal:

```bash
export PGPASSWORD='YOUR_DATABASE_PASSWORD'
```

Replace the placeholder with the actual password. Do not commit passwords to GitHub or put real credentials in the README.

The SQL workload and measurement scripts must use the same database, role, and connection settings.

## 6. OS Monitoring

The OS monitoring script collects system-level metrics using `psutil`.

**Script:** `os_monitor/monitor.py`

### Metrics collected

- UTC timestamp
- CPU utilization
- RAM utilization
- RAM used and available
- Swap utilization
- Total disk read and write bytes
- Disk read and write throughput

### Run the monitor

From the project root, with the virtual environment activated:

```bash
python -m py_compile os_monitor/monitor.py
python os_monitor/monitor.py
```

Stop monitoring with `Ctrl+C`.

### Output

The current monitor writes to:

```text
data/OS_result/query_workload_data.csv
```

The script samples system metrics at two-second intervals. The output file is append-based, so repeated runs can leave multiple monitoring periods in the same CSV.

For a clean experiment, record the start and end times of each run. Avoid deleting existing measurements unless you have backed up any data you need.

## 7. Database Workload Experiments

The database experiments use read-only SQL queries against the Olist dataset.

### 7.1 SQL workload

**Script:** `experiments/olist_workload.sql`

The workload contains ten queries covering examples such as:

- Order counts and order-status analysis
- Order counts over a date range
- Product-category revenue
- Revenue by order status
- Customers with the most orders
- Average product-item prices
- Orders grouped by customer state
- Payment values by payment type
- Review-score distributions
- Monthly order counts

Run the workload using:

```bash
psql -h localhost -U experiment_user -d olist_db \
  -v ON_ERROR_STOP=1 \
  -f experiments/olist_workload.sql
```

The SQL file enables `\timing` to display query execution times in the terminal.

### 7.2 Measure query and buffer metrics

**Script:** `experiments/measure_query_metrics.py`

This script executes the workload and collects query-level measurements using PostgreSQL `EXPLAIN (ANALYZE, BUFFERS, TIMING, FORMAT JSON)`.

Set the database password first if the script uses `PGPASSWORD`:

```bash
export PGPASSWORD='YOUR_DATABASE_PASSWORD'
```

Run:

```bash
python experiments/measure_query_metrics.py
```

The measurements include execution timing and PostgreSQL shared-buffer hit/read counts. The script writes results to:

```text
data/OS_result/query_metrics.csv
```

The file records repeated experiment runs using run identifiers. Keep these identifiers when comparing results.

**Important:** `EXPLAIN ANALYZE` executes the query. These measurements describe PostgreSQL query execution and buffer activity; they do not directly expose a complete chronological trace of physical database page IDs.

### 7.3 Compare OS measurements

**Script:** `experiments/compare_os_data.py`

Inspect the script before running it to confirm the input files and command-line arguments expected by the current version:

```bash
python experiments/compare_os_data.py
```

This is a separate OS-data comparison utility; it should not be treated as a replacement for the query-measurement script.

## 8. Synthetic Dataset Generation

**Script:** `ml/generate_dataset.py`

The current ML prototype uses a reproducible synthetic page-access trace.

### Dataset characteristics

- 10,000 page references
- 200 unique page IDs
- Fixed random seed of 42
- Hot, warm, and cold page-access groups
- Features describing page history and recency
- A target indicating whether the current page appears again within the next ten accesses

The generator uses a skewed access distribution to simulate pages with different access frequencies.

### Generate the dataset

From the project root:

```bash
python ml/generate_dataset.py
```

The generated dataset is saved to:

```text
data/processed/page_access_dataset.csv
```

The dataset includes the following columns:

| Column | Meaning |
|---|---|
| `position` | Position of the reference in the trace |
| `page_id` | Referenced page identifier |
| `previous_accesses` | Historical access count |
| `recency` | Recency-related feature |
| `recent_frequency` | Recent access-frequency feature |
| `label_accessed_soon` | Whether the page appears within the next ten references |

Regenerating the dataset replaces the input data used by later experiments. Because the random seed is fixed, the generated trace should be reproducible with the same code and environment.

## 9. Machine Learning Model

**Script:** `ml/train.py`

The initial ML model is a Random Forest classifier that predicts whether a page will be accessed again within the next ten references.

### Training procedure

1. Load the generated page-access dataset.
2. Use the engineered page-history features.
3. Split the trace chronologically into training and testing portions.
4. Train a Random Forest classifier on the training portion.
5. Evaluate predictions on the held-out portion.
6. Save the trained model artifact.

The current training script reports classification metrics, including accuracy, precision, recall, F1 score, and a confusion matrix.

### Train the model

```bash
python ml/train.py
```

The model artifact is saved as:

```text
ml/random_forest_model.joblib
```

The model predicts future-access labels. It does **not yet select an eviction victim or control PostgreSQL's buffer manager**. That requires a separate policy that converts predictions into replacement decisions and a carefully defined evaluation procedure.

## 10. Page Replacement Simulation

The simulator compares three traditional page-replacement policies using the generated page-reference trace.

### Algorithms

| Algorithm | Replacement rule |
|---|---|
| FIFO | Evicts the page that entered the frames earliest |
| LRU | Evicts the page that has not been accessed for the longest time |
| LFU | Evicts the page with the lowest access frequency, using the simulator's tie-breaking rule |

### Files

```text
page_replacement_benchmark/
├── algorithms.py
├── benchmark.py
└── results/
```

- `algorithms.py` implements the simulator and its replacement policies.
- `benchmark.py` loads the page-access dataset and executes the experiments.
- `results/benchmark_results.csv` stores the raw benchmark runs.

### Run the benchmark

```bash
python page_replacement_benchmark/benchmark.py
```

The current benchmark configuration uses:

- 10,000 page references
- Frame capacities of 8, 16, 32, and 64
- FIFO, LRU, and LFU
- Five repetitions per policy and capacity

This produces 60 benchmark records: three policies × four capacities × five repetitions.

### Benchmark metrics

- Page hits and faults
- Hit ratio and fault ratio
- Number of replacements
- Accumulated replacement-victim selection time
- Total simulation time
- Peak traced Python memory allocation

The raw results are written to:

```text
page_replacement_benchmark/results/benchmark_results.csv
```

**Reproducibility note:** Running the benchmark again overwrites this raw results CSV. Back up or rename the file first if you want to preserve earlier measurements.

The page trace and algorithmic hit/fault counts should remain the same for the same input, policies, and capacities. Timing and memory measurements can vary between runs.

## 11. Benchmark Report Generation

**Script:** `page_replacement_benchmark/report.py`

The report generator reads the raw benchmark CSV and calculates summary statistics for each algorithm and frame capacity.

It produces:

```text
page_replacement_benchmark/results/
├── benchmark_results.csv
├── summary.csv
├── benchmark_report.md
├── page_faults_comparison.png
├── hit_ratio_comparison.png
├── total_simulation_time_ms_comparison.png
├── replacement_time_us_comparison.png
└── peak_python_memory_kb_comparison.png
```

### Generate the report

First, ensure that `matplotlib` is installed and that the raw benchmark CSV exists.

```bash
python page_replacement_benchmark/report.py
```

This command reads the current benchmark results and regenerates the summary, report, and charts. It does not rerun the page-replacement simulations or overwrite the raw benchmark CSV.

If `report.py` has not yet been created in your working copy, do not run this command until the script has been added.

## 12. Complete Experiment Workflow

The following sequence runs the current collection, dataset, ML, and simulation components. Database and OS monitoring are separate experiments, so they are not automatically synchronized by this sequence.

### Step 1 — Enter the project and activate the environment

```bash
cd ~/github-project/cross-layer-db-phase2
source ~/cross-layer-db/venv/bin/activate
```

### Step 2 — Start OS monitoring

In a dedicated terminal:

```bash
cd ~/github-project/cross-layer-db-phase2
source ~/cross-layer-db/venv/bin/activate
python os_monitor/monitor.py
```

Keep it running while executing the workload you want to observe. Stop it with `Ctrl+C` after the experiment.

### Step 3 — Run the database workload

In another terminal:

```bash
cd ~/github-project/cross-layer-db-phase2
source ~/cross-layer-db/venv/bin/activate

export PGPASSWORD='YOUR_DATABASE_PASSWORD'

psql -h localhost -U experiment_user -d olist_db \
  -v ON_ERROR_STOP=1 \
  -f experiments/olist_workload.sql
```

### Step 4 — Record query measurements

```bash
python experiments/measure_query_metrics.py
```

### Step 5 — Generate the synthetic page-access dataset

```bash
python ml/generate_dataset.py
```

### Step 6 — Train the Random Forest model

```bash
python ml/train.py
```

### Step 7 — Benchmark FIFO, LRU, and LFU

```bash
python page_replacement_benchmark/benchmark.py
```

### Step 8 — Generate the benchmark report

```bash
python page_replacement_benchmark/report.py
```

### Step 9 — Inspect the results

```bash
ls -lh data/OS_result/
ls -lh data/processed/
ls -lh ml/
ls -lh page_replacement_benchmark/results/
```

Review the raw CSVs, summary report, and plots before drawing conclusions.

## 13. Results and Evaluation Metrics

The current synthetic benchmark has shown the following average hit ratios:

| Frames | FIFO | LRU | LFU |
|---:|---:|---:|---:|
| 8 | 14.85% | 15.15% | 22.59% |
| 16 | 27.22% | 29.32% | 43.75% |
| 32 | 46.26% | 51.82% | 66.05% |
| 64 | 67.87% | 75.59% | 80.27% |

For this particular synthetic trace, LFU achieved the highest hit ratio among the three simulated policies. Increasing the number of available frames reduced page faults for all three policies.

These values are **simulation results for the current synthetic workload**, not measured PostgreSQL buffer hit ratios or proof that an ML policy improves database performance.

The overall project evaluation should consider:

- Cache hit ratio and page-fault rate
- PostgreSQL shared-buffer hits and reads
- Disk I/O and memory utilization
- Query execution latency
- Throughput under repeatable workloads
- Replacement-policy overhead
- ML prediction quality
- Resource consumption and performance across different workloads

Simulation timings and peak Python memory measurements are environment-dependent. They should not be interpreted as direct estimates of PostgreSQL's internal buffer-manager cost or total process memory usage.

## 14. Project Structure

The main working directory currently follows this structure:

```text
cross-layer-db-phase2/
├── README.md
├── requirements.txt
├── .gitignore
│
├── os_monitor/
│   └── monitor.py
│
├── ml/
│   ├── generate_dataset.py
│   ├── train.py
│   └── random_forest_model.joblib
│
├── experiments/
│   ├── olist_workload.sql
│   ├── measure_query_metrics.py
│   └── compare_os_data.py
│
├── data/
│   ├── database/
│   │   └── Olist_tables.sql
│   ├── processed/
│   │   └── page_access_dataset.csv
│   ├── raw/
│   │   ├── os_metrics.csv
│   │   ├── os_metrics_sample.csv
│   │   └── [Olist source data]
│   └── OS_result/
│       ├── idle_data.csv
│       ├── query_workload_data.csv
│       ├── query_experiment_os_metrics.csv
│       └── query_metrics.csv
│
└── page_replacement_benchmark/
    ├── algorithms.py
    ├── benchmark.py
    └── results/
        ├── benchmark_results.csv
        └── [generated reports and plots]
```

This is a guide to the expected working structure. Some outputs are generated only after their corresponding scripts run, and the exact files in a local checkout may differ.

## 15. Limitations and Future Work

### Current limitations

1. **Synthetic page references:** The replacement simulator does not yet use a real PostgreSQL page-ID access trace.
2. **Prediction versus replacement:** The Random Forest predicts whether a page will be accessed soon, but it does not yet decide which page to evict.
3. **Cross-layer integration:** OS metrics and query metrics are collected separately; they are not yet joined into one fully synchronized training dataset.
4. **Simulation versus production:** FIFO, LRU, and LFU are evaluated in a Python simulator, not by replacing PostgreSQL's internal buffer-manager policy.
5. **Workload coverage:** Results depend on the current synthetic trace and need validation against additional workloads.

### Planned improvements

- Align OS metrics and query measurements using timestamps and experiment IDs.
- Extract or construct a suitable chronological database page-access trace.
- Improve feature engineering using workload history and OS state.
- Evaluate prediction quality with suitable held-out workloads.
- Design an ML-assisted eviction policy using predicted reuse or access probability.
- Compare the ML policy against FIFO, LRU, LFU, and potentially LRU-K.
- Evaluate query latency, I/O, hit ratio, and resource consumption under controlled conditions.
- Repeat experiments and document the limitations of each comparison.
- Explore a safe PostgreSQL integration strategy without modifying production data or relying on unsupported internal interfaces.

## 16. Troubleshooting

### Python cannot import a package

Activate the virtual environment and install the missing dependency:

```bash
source ~/cross-layer-db/venv/bin/activate
python -m pip install PACKAGE_NAME
```

### PostgreSQL connection fails

Check the service:

```bash
sudo systemctl status postgresql
```

Verify the database, role, and connection settings. Use `experiment_user` rather than assuming a database role named after the Ubuntu account exists.

### The benchmark cannot find the dataset

Run the generator from the project root:

```bash
python ml/generate_dataset.py
```

Then rerun the benchmark:

```bash
python page_replacement_benchmark/benchmark.py
```

### The report generator cannot find `matplotlib`

```bash
python -m pip install matplotlib
```

Confirm that `page_replacement_benchmark/results/benchmark_results.csv` exists before generating the report.

### Benchmark timings differ between runs

Timing and traced memory can vary due to system load, Python overhead, and the execution environment. Use the average across repetitions and focus on reproducible page-fault and hit-ratio results for the same trace.

---

**Project principle:** Keep experiments reproducible, distinguish simulated results from real database measurements, and do not claim ML-based replacement improvements until the ML policy has been integrated and evaluated against appropriate baselines.
