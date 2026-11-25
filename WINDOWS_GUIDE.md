# Windows Guide & Database Demonstration
## ML-Based Cross-Layer Database Buffer & Memory Management

**Team:** Kasukabe Coders  
**Team ID:** OSDBMS-V-06-T276  
**Institution:** Graphic Era (Deemed to be University), Dehradun  
**Academic session:** 2026–27  
**Repository:** https://github.com/Dhruvrawat741/ML-Based-Cross-Layer-Database-Buffer-Memory-Management

### Team responsibilities
- **Dhruv Singh Rawat (Team Lead):** DBMS, Python, OS and cross-layer integration.
- **Harsh Raj:** DBMS workstream.
- **Anant Chauhan:** OS monitoring workstream.
- **Mentor:** Dr. Upma Jain.

---

## 1. Assumptions

This guide assumes the following are already installed and configured on Windows:

- Python 3 and Git
- PostgreSQL server and pgAdmin 4
- Project repository cloned locally
- Python virtual environment at `cross_layer_db\venv`
- Python dependencies installed from `requirements.txt`
- PostgreSQL database `olist_db`
- Schema `cachelab`, its tables, views, trigger, function and procedure
- Login role `cachelab_app` with the required permissions

The SQL setup creates the dashboard's `cachelab` objects. It does **not** import the Olist e-commerce dataset or copy the contents of a different computer's database.

## 2. Run the project on Windows

Open PowerShell and move into the project directory:

```powershell
cd "$HOME\github-project\ML-Based-Cross-Layer-Database-Buffer-Memory-Management\cross_layer_db"
```

Activate the virtual environment:

```powershell
.\venv\Scripts\Activate.ps1
```

If script execution is blocked, run this in the current PowerShell process and activate again:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\venv\Scripts\Activate.ps1
```

Set database connection variables in the same terminal. Replace the sample with the actual password assigned to `cachelab_app`:

```powershell
$env:DB_HOST = "127.0.0.1"
$env:DB_PORT = "5432"
$env:DB_NAME = "olist_db"
$env:DB_USER = "cachelab_app"
$env:DB_PASSWORD = "YOUR_ACTUAL_PASSWORD"
```

Test the connection:

```powershell
python -c "import psycopg; c=psycopg.connect(host='127.0.0.1',port=5432,dbname='olist_db',user='cachelab_app',password='YOUR_ACTUAL_PASSWORD'); print('Database connected successfully'); c.close()"
```

Start Streamlit:

```powershell
python -m streamlit run dashboard/app.py
```

Open **http://localhost:8501**. Keep the terminal open while the dashboard is running.

> The environment variables are temporary and must be set again in a new PowerShell session. Do not commit database passwords to GitHub.

---

## 3. Open the database in pgAdmin 4

1. Launch pgAdmin 4.
2. Expand **Servers → your PostgreSQL server → Databases**.
3. Select **olist_db**.
4. Right-click `olist_db` and choose **Query Tool**.
5. Confirm that the Query Tool is connected to `olist_db`, not the default `postgres` database.

Run the following SQL examples in Query Tool.

## 4. Show database tables

List the project's base tables:

```sql
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'cachelab'
  AND table_type = 'BASE TABLE'
ORDER BY table_name;
```

Expected tables:

- `workloads`
- `policies`
- `experiments`
- `experiment_metrics`
- `audit_logs`

Show columns and data types:

```sql
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_schema = 'cachelab'
  AND table_name = 'workloads'
ORDER BY ordinal_position;
```

Show the four replacement policies:

```sql
SELECT * FROM cachelab.policies ORDER BY policy_id;
```

Expected policy names: FIFO, LRU, LFU and ML.

## 5. Demonstrate views

### Workload catalog view

```sql
SELECT * FROM cachelab.workload_catalog_view;
```

Explain that this view presents workload information from the `workloads` table in a reusable query.

### Policy comparison view

```sql
SELECT *
FROM cachelab.policy_comparison_view
ORDER BY experiment_id DESC, policy_name;
```

Explain that the view combines experiments, workloads, experiment metrics and policies. It can return zero rows before the first benchmark is saved.

## 6. Demonstrate the audit trigger

Show the trigger registration:

```sql
SELECT
    trigger_name,
    event_manipulation,
    event_object_table,
    action_statement
FROM information_schema.triggers
WHERE trigger_schema = 'cachelab'
ORDER BY trigger_name, event_manipulation;
```

Show its definition:

```sql
SELECT pg_get_triggerdef(oid)
FROM pg_trigger
WHERE tgname = 'workload_audit_trigger';
```

Insert a temporary test workload:

```sql
INSERT INTO cachelab.workloads (workload_name, description)
VALUES ('Teacher Demo', 'Testing the audit trigger');
```

Inspect the audit log:

```sql
SELECT *
FROM cachelab.audit_logs
ORDER BY audit_id DESC
LIMIT 10;
```

Expected result: an audit entry for the INSERT on `workloads`. The trigger also handles UPDATE and DELETE operations. Use a test row for demonstration; do not delete real project data.

**Explanation:** The trigger automatically records workload-table INSERT, UPDATE and DELETE events in `audit_logs`.

## 7. Demonstrate the stored function

Run:

```sql
SELECT cachelab.get_workload_count();
```

Explanation: the function returns the current number of rows in `cachelab.workloads`.

Show the function definition:

```sql
SELECT pg_get_functiondef(
    'cachelab.get_workload_count()'::regprocedure
);
```

## 8. Demonstrate the stored procedure

First find a valid workload ID:

```sql
SELECT workload_id, workload_name, description
FROM cachelab.workloads
ORDER BY workload_id;
```

Use an ID from the result. The example below uses ID 1; replace it if needed:

```sql
CALL cachelab.update_workload_description(
    1,
    'Updated during project demonstration'
);

SELECT *
FROM cachelab.workloads
WHERE workload_id = 1;
```

Explanation: the procedure updates the description of the selected workload. A function returns a value; a procedure is called to perform an operation.

## 9. Demonstrate the JOIN query

```sql
SELECT
    e.experiment_id,
    w.workload_name,
    e.experiment_name,
    p.policy_name,
    m.cache_hits,
    m.page_faults,
    m.hit_ratio
FROM cachelab.experiments e
JOIN cachelab.workloads w
    ON e.workload_id = w.workload_id
JOIN cachelab.experiment_metrics m
    ON e.experiment_id = m.experiment_id
JOIN cachelab.policies p
    ON m.policy_id = p.policy_id
ORDER BY e.experiment_id DESC, p.policy_name;
```

Explain the relationships:

- `workloads.workload_id` connects to `experiments.workload_id`.
- `experiments.experiment_id` connects to `experiment_metrics.experiment_id`.
- `policies.policy_id` connects to `experiment_metrics.policy_id`.

## 10. Demonstrate the Streamlit dashboard

### Overview & Benchmark
1. Open **Overview & Benchmark**.
2. Configure reference count, page universe, cache capacity and locality, or upload an ordered page-reference CSV.
3. Run FIFO, LRU, LFU and ML.
4. Show the comparison metrics and charts.
5. Download CSV or JSON results if requested.

### SQL Query Lab
1. Open **SQL Query Lab**.
2. Execute a single statement, for example:

   `SELECT * FROM cachelab.policies;`

3. Show the returned data.
4. Data-changing statements require confirmation. DDL and multiple statements are blocked by design.

### Experiment History
After saving a benchmark, open **Experiment History** to show the experiment and per-policy metrics persisted in PostgreSQL.

## 11. Optional page-reference CSV

The prepared file `page_reference_trace.csv` contains one ordered column named `page_id` and 660 synthetic page references. Upload it through the CSV upload control on Overview & Benchmark.

This is a synthetic test trace, not a captured PostgreSQL logical page-reference stream.

## 12. Suggested teacher demonstration order

1. Show tables and columns.
2. Show the policies table.
3. Run the workload catalog view.
4. Run the policy comparison view.
5. Show the trigger definition, insert a test workload and inspect the audit log.
6. Call the workload-count function.
7. Call the update-description procedure.
8. Run the multi-table JOIN query.
9. Run all four policies in Streamlit.
10. Show the saved run in Experiment History.

## 13. Troubleshooting

### Password authentication failed
Reset the `cachelab_app` password in pgAdmin as a PostgreSQL administrator, then update `DB_PASSWORD` in PowerShell. Do not use an example password literally.

### Too many connections
Close unused pgAdmin Query Tool tabs and old Streamlit sessions. As an administrator connected to the `postgres` database, inspect stale sessions before terminating them. Do not increase `max_connections` without diagnosing the cause.

### Permission denied for policy_comparison_view
As a PostgreSQL administrator connected to `olist_db`, run:

```sql
GRANT USAGE ON SCHEMA cachelab TO cachelab_app;
GRANT SELECT ON cachelab.policy_comparison_view TO cachelab_app;
```

### dashboard/app.py does not exist
Make sure PowerShell is in the repository's `cross_layer_db` directory, not the deleted legacy `cross-layer-db-phase2` directory.

### Experiment History is empty
Run and save at least one benchmark. Experiment History displays persisted benchmark runs.

---

## 14. Measurement notes and limitations

- The built-in generator creates a synthetic trace; uploaded traces are only as representative as their source.
- Simulator cache hit ratios and page faults are not PostgreSQL shared-buffer hit ratios.
- PostgreSQL `EXPLAIN (ANALYZE, BUFFERS)` and `pg_buffercache` snapshots do not provide a complete chronological logical page-reference trace.
- The ML component uses snapshot-derived page features to rank eviction candidates. Snapshot evaluation is not a logical page-reference hit-rate simulation.
- Python memory measurements are not PostgreSQL server memory measurements.
- Do not claim production performance improvement without controlled, reproducible experiments.

## 15. Team contribution mapping

- **Dhruv Singh Rawat:** Team Lead; DBMS, Python, OS and cross-layer integration.
- **Harsh Raj:** DBMS workstream.
- **Anant Chauhan:** OS monitoring workstream.
- **Mentor:** Dr. Upma Jain.

**Project:** ML-Based Cross-Layer Database Buffer & Memory Management  
**Team:** Kasukabe Coders | **Team ID:** OSDBMS-V-06-T276
