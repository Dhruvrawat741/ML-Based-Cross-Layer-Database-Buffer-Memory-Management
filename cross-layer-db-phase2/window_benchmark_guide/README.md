# Windows Guide: Run the Page Replacement Benchmark

This guide explains how to run the page-replacement algorithms on a
Windows PC and inspect the results locally.

The benchmark compares **FIFO**, **LRU**, and **LFU** using a
page-access trace. It reports page faults, hit ratio, execution timing,
and Python memory-allocation measurements. It is a simulator; it does
not replace PostgreSQL's internal buffer manager.

## 1. Requirements

-   Windows 10 or 11
-   Git
-   Python 3.10 or newer
-   PowerShell

Check that Git and Python are available:

``` powershell
git --version
python --version
```

If `python` is not recognized, install Python from
https://www.python.org/downloads/ and enable **Add Python to PATH**
during installation. Close and reopen PowerShell after installation. The
Windows `py` launcher is optional; these instructions use `python`.

## 2. Clone the repository

``` powershell
cd $HOME
git clone https://github.com/Dhruvrawat741/ML-Based-Cross-Layer-Database-Buffer-Memory-Management.git
cd .\ML-Based-Cross-Layer-Database-Buffer-Memory-Management\cross-layer-db-phase2
```

If you already cloned the repository, navigate to the existing project
folder instead:

``` powershell
cd "$HOME\ML-Based-Cross-Layer-Database-Buffer-Memory-Management\cross-layer-db-phase2"
```

Confirm that you are in the project root:

``` powershell
Get-Location
Get-ChildItem
```

## 3. Create and activate a virtual environment

Run these commands from the project root:

``` powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks script execution, allow scripts for this PowerShell
process only, then activate again:

``` powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

The prompt should now begin with `(.venv)`.

## 4. Install benchmark dependencies

``` powershell
python -m pip install --upgrade pip
python -m pip install pandas matplotlib
python -c "import pandas, matplotlib; print('Dependencies installed successfully')"
```

## 5. Check the dataset

The benchmark reads the generated page-access dataset at
`data/processed/page_access_dataset.csv`.

``` powershell
Test-Path .\data\processed\page_access_dataset.csv
```

If the result is `False`, generate it from the project root:

``` powershell
python .\ml\generate_dataset.py
```

## 6. Run the page-replacement benchmark

Run scripts from the project root (`cross-layer-db-phase2`), not from
inside the benchmark subfolder, because the project scripts use paths
relative to the project root.

Inspect the available scripts:

``` powershell
Get-ChildItem .\page_replacement_benchmark
```

If the repository contains `pybench.py`, run:

``` powershell
python .\page_replacement_benchmark\pybench.py
```

If it instead contains `benchmark.py`, run:

``` powershell
python .\page_replacement_benchmark\benchmark.py
```

Use the filename that actually exists in your cloned repository; do not
run both unless the project documentation explicitly says to.

## 7. Generate the report and graphs

If the folder contains `report.py`, run:

``` powershell
python .\page_replacement_benchmark\report.py
```

## 8. View your results

``` powershell
Get-ChildItem .\page_replacement_benchmark\results
```

Expected output files, depending on the project version:

-   `benchmark_results.csv` --- detailed results
-   `summary.csv` --- aggregated results
-   `benchmark_report.md` --- written report
-   `page_faults_comparison.png` --- page-fault comparison
-   `hit_ratio_comparison.png` --- hit-ratio comparison
-   `total_simulation_time_ms_comparison.png` --- total simulation time
-   `replacement_time_us_comparison.png` --- time spent selecting
    replacement victims
-   `peak_python_memory_kb_comparison.png` --- peak Python allocations
    measured by `tracemalloc`

Print the detailed CSV:

``` powershell
python -c "import pandas as pd; print(pd.read_csv('page_replacement_benchmark/results/benchmark_results.csv').to_string(index=False))"
```

Print the summary:

``` powershell
python -c "import pandas as pd; print(pd.read_csv('page_replacement_benchmark/results/summary.csv').to_string(index=False))"
```

Open the result folder in VS Code:

``` powershell
code .\page_replacement_benchmark\results
```

You can open PNG files in VS Code or open the results folder using File
Explorer.

## 9. What do the metrics mean?

-   **Page faults:** references not found in the simulated frames. Lower
    is generally better for the same trace and capacity.
-   **Hit ratio:** fraction of references found in the frames. Higher is
    generally better.
-   **Total simulation time:** elapsed time for the simulator
    implementation. This varies by computer and system load.
-   **Replacement time:** time measured for selecting replacement
    victims; check the script/report for its exact definition.
-   **Peak Python memory:** Python allocations observed by
    `tracemalloc`, not total system RAM or PostgreSQL memory.

Results depend on the trace, frame capacities, algorithm implementation,
and computer. Runtime values from different PCs should not be treated as
directly comparable without accounting for hardware and system load.

## 10. Troubleshooting

### `python` is not recognized

``` powershell
where.exe python
```

Install Python, enable **Add Python to PATH**, and reopen PowerShell. If
Conda is installed and active, `python` may refer to a Conda
environment.

### `py` is not recognized

The optional Python launcher is unavailable. Use `python` instead.

### `Activate.ps1` is not recognized

The environment may not have been created. Run:

``` powershell
python -m venv .venv
Test-Path .\.venv\Scripts\Activate.ps1
```

If the check returns `True`, activate it:

``` powershell
.\.venv\Scripts\Activate.ps1
```

### PowerShell blocks script execution

``` powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

### `ModuleNotFoundError` for pandas or matplotlib

Activate `.venv`, then run:

``` powershell
python -m pip install pandas matplotlib
```

### Dataset file not found

From the project root:

``` powershell
python .\ml\generate_dataset.py
```

Then retry the benchmark.

### `pybench.py` or `benchmark.py` cannot be found

``` powershell
Get-ChildItem .\page_replacement_benchmark
```

Run the script that actually exists. Filenames are not interchangeable.

### `benchmark_results.csv` does not exist

The benchmark may not have completed, or the script may save results to
another path. Read the terminal error and inspect:

``` powershell
Get-ChildItem .\page_replacement_benchmark\results
```

Run the benchmark before running `report.py`.

### Summary or graphs are missing

Run the report generator after a successful benchmark:

``` powershell
python .\page_replacement_benchmark\report.py
```

## 11. Re-running the experiment

Activate the environment, ensure the dataset exists, and run the
benchmark and report scripts again. The benchmark may overwrite existing
results depending on the implementation. Copy any results you need to
preserve before rerunning.

## 12. Scope and limitations

This is a local simulation of FIFO, LRU, and LFU against a supplied
page-access trace. It does **not** directly control PostgreSQL's
internal buffer replacement policy. The current ML prediction model is
not automatically integrated into these algorithms unless that
integration is implemented separately.

For reproducible comparisons, use the same dataset, frame capacities,
number of repetitions, and code version. Report both
page-fault/hit-ratio results and timing results, and note the machine
used.
