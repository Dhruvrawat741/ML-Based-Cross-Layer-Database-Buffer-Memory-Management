# Cross-Layer Cache Lab — Windows and Linux

## Windows (PowerShell)
```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r dashboard\requirements.txt
streamlit run dashboard\app.py
```
If PowerShell blocks activation, run: Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

## Ubuntu / macOS
```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r dashboard/requirements.txt
streamlit run dashboard/app.py
```
Open http://localhost:8501 in your browser.

## Use
1. Configure reference count, page universe and cache capacity.
2. Click Run all four policies.
3. FIFO, LRU, LFU and ML receive the same ordered trace and cache capacity.
4. Compare hit ratio, page faults, evictions, decision time, total simulation time and Python peak memory.
5. Download CSV/JSON; timestamped results are saved in dashboard/results/.
6. To test an ordered trace, upload a CSV with a page_id column.

## Methodology
The built-in generator produces a reproducible synthetic mixed-locality trace. It is not a live PostgreSQL page-reference trace. PostgreSQL aggregate EXPLAIN (ANALYZE, BUFFERS) and pg_buffercache snapshots do not expose the ordered logical page-reference stream required for a true cache hit-ratio simulation. Do not report generated-trace hit ratios as measured PostgreSQL hit ratios.

The ML policy is a separate Random Forest model trained on a separately generated trace to predict reuse distance from past-only features. It evicts the resident page with the largest predicted reuse distance. All four policies are evaluated on the exact same trace. Training time is reported separately. Timing and Python memory depend on the machine; peak Python memory excludes PostgreSQL server and OS memory.
