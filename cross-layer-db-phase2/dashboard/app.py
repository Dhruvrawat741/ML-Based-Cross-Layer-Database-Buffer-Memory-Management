from __future__ import annotations
import json, time, tracemalloc, re
from collections import Counter, deque
from datetime import datetime
from pathlib import Path
import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st
from sklearn.ensemble import RandomForestRegressor

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"
RESULTS.mkdir(parents=True, exist_ok=True)
POLICIES = ["FIFO", "LRU", "LFU", "ML"]

def make_trace(n_refs, n_pages, seed, locality, scan_pct):
    """Repeatable mixed-locality trace; synthetic, not a captured PostgreSQL trace."""
    rng = np.random.default_rng(seed)
    hot = max(2, min(n_pages, locality))
    weights = 1 / np.arange(1, hot + 1, dtype=float) ** 1.12
    weights /= weights.sum()
    trace, scan_pos = [], 0
    scan_len = max(2, n_pages // 3)
    for _ in range(n_refs):
        mode = rng.random()
        if mode < scan_pct / 100:
            trace.append(f"page_{scan_pos % scan_len:06d}")
            scan_pos += 1
        elif mode < 0.88:
            trace.append(f"page_{int(rng.choice(hot, p=weights)):06d}")
        else:
            trace.append(f"page_{int(rng.integers(0, n_pages)):06d}")
    return trace

def features_for(page, now, seen, counts, last_gap):
    first, last = seen.get(page, (now, now))
    return [float(counts[page]), float(now-last), float(now-first),
            float(last_gap.get(page, 0)), float((now-last)/max(1, counts[page]))]

def train_ml(seed, locality, n_pages):
    train = make_trace(18000, n_pages, seed+7919, locality, 8)
    positions = {}
    for i, page in enumerate(train):
        positions.setdefault(page, deque()).append(i)
    seen, counts, last_gap, X, y = {}, Counter(), {}, [], []
    for i, page in enumerate(train):
        q = positions[page]
        gap = q[1]-i if len(q)>1 else len(train)
        X.append(features_for(page, i, seen, counts, last_gap))
        y.append(float(np.log1p(gap)))
        old = seen.get(page)
        last_gap[page] = i-old[1] if old else 0
        seen[page] = (old[0], i) if old else (i, i)
        counts[page] += 1
        q.popleft()
    model = RandomForestRegressor(n_estimators=45, max_depth=12, min_samples_leaf=3,
                                  random_state=seed, n_jobs=-1)
    start = time.perf_counter()
    model.fit(np.asarray(X, dtype=np.float32), np.asarray(y, dtype=np.float32))
    return model, (time.perf_counter()-start)*1000

def simulate(trace, capacity, policy, model=None):
    cache, arrival, last = set(), {}, {}
    counts, seen, last_gap = Counter(), {}, {}
    hits = faults = evictions = decision_ns = inference_ns = 0
    tracemalloc.start()
    total_start = time.perf_counter_ns()
    for i, page in enumerate(trace):
        if page in cache:
            hits += 1
        else:
            faults += 1
            if len(cache) >= capacity:
                d0 = time.perf_counter_ns()
                if policy == "FIFO":
                    victim = min(cache, key=lambda p: arrival[p])
                elif policy == "LRU":
                    victim = min(cache, key=lambda p: last[p])
                elif policy == "LFU":
                    victim = min(cache, key=lambda p: (counts[p], last[p]))
                else:
                    candidates = list(cache)
                    matrix = np.asarray([features_for(p, i, seen, counts, last_gap)
                                         for p in candidates], dtype=np.float32)
                    t0 = time.perf_counter_ns()
                    scores = model.predict(matrix)
                    inference_ns += time.perf_counter_ns()-t0
                    victim = candidates[int(np.argmax(scores))]
                decision_ns += time.perf_counter_ns()-d0
                cache.remove(victim)
                arrival.pop(victim, None); last.pop(victim, None)
                evictions += 1
            cache.add(page); arrival[page] = i
        old = seen.get(page)
        last_gap[page] = i-old[1] if old else 0
        seen[page] = (old[0], i) if old else (i, i)
        counts[page] += 1
        last[page] = i
    elapsed_ms = (time.perf_counter_ns()-total_start)/1e6
    _, peak_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return {"policy":policy, "references":len(trace), "hits":hits, "page_faults":faults,
            "hit_ratio_pct":hits/len(trace)*100, "fault_ratio_pct":faults/len(trace)*100,
            "evictions":evictions, "decision_time_ms":decision_ns/1e6,
            "ml_inference_time_ms":inference_ns/1e6, "total_simulation_time_ms":elapsed_ms,
            "peak_python_memory_mb":peak_bytes/(1024*1024), "cache_capacity_pages":capacity}


def save_to_postgres(workload_label, capacity, result, seed):
    """Persist the dashboard's measured policy results to PostgreSQL."""
    import os
    import psycopg

    conn = psycopg.connect(
        host=os.getenv("DB_HOST", "127.0.0.1"),
        port=os.getenv("DB_PORT", "5432"),
        dbname=os.getenv("DB_NAME", "olist_db"),
        user=os.getenv("DB_USER", "cachelab_app"),
        password=os.getenv("DB_PASSWORD", ""),
        connect_timeout=5,
    )
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO cachelab.workloads (workload_name, description)
                    VALUES (%s, %s) RETURNING workload_id
                    """,
                    (workload_label, "Dashboard workload; seed=" + str(seed)),
                )
                workload_id = cur.fetchone()[0]
                cur.execute(
                    """
                    INSERT INTO cachelab.experiments
                        (workload_id, experiment_name, cache_capacity, status)
                    VALUES (%s, %s, %s, 'COMPLETED')
                    RETURNING experiment_id
                    """,
                    (workload_id, "Dashboard comparison seed " + str(seed), int(capacity)),
                )
                experiment_id = cur.fetchone()[0]
                for row in result.to_dict("records"):
                    cur.execute(
                        """
                        INSERT INTO cachelab.experiment_metrics
                            (experiment_id, policy_id, total_references, cache_hits,
                             page_faults, evictions, hit_ratio, execution_time_ms,
                             memory_usage_mb)
                        SELECT %s, policy_id, %s, %s, %s, %s, %s, %s, %s
                        FROM cachelab.policies WHERE policy_name = %s
                        """,
                        (
                            experiment_id, int(row["references"]), int(row["hits"]),
                            int(row["page_faults"]), int(row["evictions"]),
                            float(row["hit_ratio_pct"]) / 100.0,
                            float(row["total_simulation_time_ms"]),
                            float(row["peak_python_memory_mb"]), str(row["policy"]),
                        ),
                    )
        return experiment_id
    finally:
        conn.close()


def benchmark_page():
    st.title("Policy Benchmark")
    st.caption("Compare FIFO, LRU, LFU and ML on the same page-reference trace.")
    with st.expander("Measurement methodology and limitations"):
        st.markdown("""
        - All four policies receive the same ordered page-reference trace and cache capacity.
        - Hit ratio and page faults are calculated by the simulator from that trace.
        - The built-in generator creates a synthetic mixed-locality workload, not a live PostgreSQL page trace.
        - Upload a CSV with an ordered page_id column to test a supplied page-reference trace.
        - ML is a separate Random Forest reuse-distance predictor trained on a separate generated trace using past-only features.
        - Timing and Python memory are measured on this machine and vary by hardware/OS.
        """)
    st.sidebar.header("Benchmark configuration")
    source = st.sidebar.radio("Workload source", ["Generate workload", "Upload page-reference CSV"])
    refs = st.sidebar.slider("Number of references", 2000, 50000, 12000, 1000)
    pages = st.sidebar.slider("Unique page universe", 100, 5000, 800, 50)
    capacity = st.sidebar.slider("Cache capacity (pages)", 16, 1000, 128, 16)
    locality = st.sidebar.slider("Hot working-set size", 10, 1000, 160, 10)
    scan_pct = st.sidebar.slider("Sequential scan share (%)", 0, 50, 8, 1)
    seed = st.sidebar.number_input("Random seed", 1, 999999, 42)
    uploaded = st.sidebar.file_uploader("CSV with ordered page_id column", type=["csv"]) if source.startswith("Upload") else None
    run = st.sidebar.button("▶ Run all four policies", type="primary", use_container_width=True)
    if run:
        if source.startswith("Upload"):
            if uploaded is None:
                st.error("Upload a CSV first."); st.stop()
            frame = pd.read_csv(uploaded)
            if "page_id" not in frame.columns or frame.empty:
                st.error("CSV must contain a non-empty page_id column in reference order."); st.stop()
            trace = frame["page_id"].dropna().astype(str).tolist()
            if len(trace) < 100:
                st.error("Provide at least 100 page references."); st.stop()
            label = f"Uploaded trace ({len(trace):,} references)"
        else:
            trace = make_trace(int(refs), int(pages), int(seed), int(locality), int(scan_pct))
            label = "Generated synthetic workload (not captured PostgreSQL trace)"
        with st.spinner("Training ML predictor and running identical trace through all policies..."):
            model, training_ms = train_ml(int(seed), int(locality), int(pages))
            rows = [simulate(trace, int(capacity), p, model) for p in POLICIES]
        result = pd.DataFrame(rows)
        result.insert(1, "workload", label)
        result["ml_training_time_ms"] = 0.0
        result.loc[result.policy=="ML", "ml_training_time_ms"] = training_ms
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_path, json_path = RESULTS/f"policy_comparison_{stamp}.csv", RESULTS/f"policy_comparison_{stamp}.json"
        result.to_csv(csv_path, index=False)
        json_path.write_text(json.dumps({"workload":label,"seed":int(seed),"trace_references":len(trace),
            "unique_pages":len(set(trace)),"capacity":int(capacity),"ml_training_time_ms":training_ms,
            "results":rows}, indent=2), encoding="utf-8")
        db_experiment_id = None
        db_error = None
        try:
            db_experiment_id = save_to_postgres(label, int(capacity), result, int(seed))
        except Exception as exc:
            db_error = str(exc)
        st.session_state["result"] = result
        st.session_state["meta"] = {"label":label,"csv":str(csv_path),"json":str(json_path),"training":training_ms,"db_experiment_id":db_experiment_id}
        st.success(f"Completed. Saved CSV and JSON in {RESULTS}")
        if db_experiment_id is not None:
            st.success(f"Saved experiment #{db_experiment_id} and all four policy results to PostgreSQL.")
        else:
            st.warning(f"PostgreSQL save failed (local CSV/JSON are safe): {db_error}")
    if "result" in st.session_state:
        result, meta = st.session_state["result"], st.session_state["meta"]
        st.subheader("Latest benchmark")
        st.info(f"{meta['label']} · ML training: {meta['training']:.2f} ms · Saved in {RESULTS}")
        cols = st.columns(4)
        metrics = [("hit_ratio_pct","Best hit ratio","max","{:.2f}%"),
                   ("page_faults","Fewest page faults","min","{:,.0f}"),
                   ("total_simulation_time_ms","Fastest simulation","min","{:.2f} ms"),
                   ("peak_python_memory_mb","Lowest peak Python memory","min","{:.3f} MB")]
        for col,(key,label,mode,fmt) in zip(cols,metrics):
            idx = result[key].idxmax() if mode=="max" else result[key].idxmin()
            col.metric(label, result.loc[idx,"policy"]+" · "+fmt.format(result.loc[idx,key]))
        st.dataframe(result.round(4), use_container_width=True, hide_index=True)
        c1,c2 = st.columns(2)
        with c1:
            st.plotly_chart(px.bar(result,x="policy",y="hit_ratio_pct",color="policy",color_discrete_sequence=["#0f8b8d", "#2563a6", "#62a89f", "#e0a458"],title="Cache hit ratio (%)",text_auto=".2f"),use_container_width=True)
            st.plotly_chart(px.bar(result,x="policy",y="page_faults",color="policy",title="Page faults",text_auto=True),use_container_width=True)
            st.plotly_chart(px.bar(result,x="policy",y="decision_time_ms",color="policy",title="Victim-selection time (ms)",text_auto=".3f"),use_container_width=True)
        with c2:
            st.plotly_chart(px.bar(result,x="policy",y="total_simulation_time_ms",color="policy",title="Total simulation time (ms)",text_auto=".2f"),use_container_width=True)
            st.plotly_chart(px.bar(result,x="policy",y="peak_python_memory_mb",color="policy",title="Peak Python memory (MB)",text_auto=".3f"),use_container_width=True)
            st.plotly_chart(px.bar(result,x="policy",y="evictions",color="policy",title="Page evictions",text_auto=True),use_container_width=True)
        st.download_button("Download comparison CSV",result.to_csv(index=False).encode("utf-8"),"policy_comparison.csv","text/csv")
        st.download_button("Download comparison JSON",json.dumps(result.to_dict("records"),indent=2).encode("utf-8"),"policy_comparison.json","application/json")
    else:
        st.info("Configure the workload and click Run all four policies to collect metrics and render graphs.")


def db_connection():
    import os
    import psycopg
    return psycopg.connect(
        host=os.getenv("DB_HOST", "127.0.0.1"),
        port=os.getenv("DB_PORT", "5432"),
        dbname=os.getenv("DB_NAME", "olist_db"),
        user=os.getenv("DB_USER", "cachelab_app"),
        password=os.getenv("DB_PASSWORD", ""),
        connect_timeout=5,
    )


def query_lab():
    st.title("SQL Query Lab")
    st.caption("Run SQL against your olist_db database and inspect the returned rows.")
    st.info("Allowed: SELECT, INSERT, UPDATE, DELETE and CALL. Data-changing statements require confirmation. DDL, transaction-control commands and multiple statements are blocked.")
    examples = {
        "Choose an example": "",
        "View workloads": "SELECT * FROM cachelab.workload_catalog_view ORDER BY workload_id;",
        "Compare policies": "SELECT * FROM cachelab.policy_comparison_view ORDER BY experiment_id DESC, policy_name;",
        "Count workloads (function)": "SELECT cachelab.get_workload_count();",
        "Update description (procedure)": "CALL cachelab.update_workload_description(1, 'Updated from SQL Query Lab');",
        "Recent audit entries": "SELECT * FROM cachelab.audit_logs ORDER BY 1 DESC LIMIT 20;",
    }
    example = st.selectbox("SQL examples", list(examples.keys()))
    if "sql_editor" not in st.session_state:
        st.session_state.sql_editor = examples["Compare policies"]
    if example != "Choose an example" and st.button("Load example"):
        st.session_state.sql_editor = examples[example]
    sql_text = st.text_area("SQL statement", key="sql_editor", height=190,
                            placeholder="SELECT * FROM cachelab.workloads;")
    confirm = st.checkbox("I confirm that I want to execute this data-changing statement.")
    if st.button("▶ Execute SQL", type="primary"):
        import sqlparse
        statements = [s for s in sqlparse.parse(sql_text) if str(s).strip()]
        if len(statements) != 1:
            st.error("Enter exactly one SQL statement.")
            return
        statement = statements[0]
        sql_type = statement.get_type().upper()
        # Reject WITH/CTE, DDL, transaction control, and every command outside this allowlist.
        first_keyword = next((t.normalized.upper() for t in statement.tokens
                              if not t.is_whitespace and not t.is_comment), "")
        allowed = {"SELECT", "INSERT", "UPDATE", "DELETE", "CALL"}
        if first_keyword not in allowed:
            st.error("Only one SELECT, INSERT, UPDATE, DELETE or CALL statement is permitted.")
            return
        if sql_type in {"INSERT", "UPDATE", "DELETE", "CALL"} and not confirm:
            st.warning("Tick the confirmation checkbox before executing a data-changing statement.")
            return
        try:
            with db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(sql_text)
                    if cur.description:
                        rows = cur.fetchall()
                        columns = [d.name for d in cur.description]
                        out = pd.DataFrame(rows, columns=columns)
                        st.session_state.sql_result = out
                        st.session_state.sql_message = f"Query successful · {len(out):,} row(s) returned"
                    else:
                        st.session_state.sql_result = None
                        st.session_state.sql_message = f"Statement successful · {cur.rowcount} row(s) affected"
            st.success(st.session_state.sql_message)
        except Exception as exc:
            st.error(f"SQL execution failed: {exc}")
    if st.session_state.get("sql_message") and st.session_state.get("sql_result") is not None:
        st.caption(st.session_state.sql_message)
        st.dataframe(st.session_state.sql_result, use_container_width=True, hide_index=True)
        st.download_button("Download query result CSV",
            st.session_state.sql_result.to_csv(index=False).encode("utf-8"),
            "query_result.csv", "text/csv")
    elif st.session_state.get("sql_message"):
        st.success(st.session_state.sql_message)


def experiment_history_page():
    st.title("Experiment History")
    st.caption("Previously persisted benchmark runs from PostgreSQL.")
    try:
        with db_connection() as conn:
            history = pd.read_sql_query("""
                SELECT e.experiment_id, e.experiment_name, w.workload_name,
                       e.cache_capacity, p.policy_name, m.total_references,
                       m.cache_hits, m.page_faults,
                       ROUND((m.hit_ratio * 100)::numeric, 2) AS hit_ratio_percent,
                       m.execution_time_ms, m.memory_usage_mb
                FROM cachelab.experiments e
                JOIN cachelab.workloads w ON w.workload_id=e.workload_id
                JOIN cachelab.experiment_metrics m ON m.experiment_id=e.experiment_id
                JOIN cachelab.policies p ON p.policy_id=m.policy_id
                ORDER BY e.experiment_id DESC, p.policy_name
            """, conn)
        st.dataframe(history, use_container_width=True, hide_index=True)
    except Exception as exc:
        st.error(f"Could not load experiment history: {exc}")


def main():
    st.set_page_config(page_title="Cross-Layer DB Lab", page_icon="🧠", layout="wide")
    px.defaults.template = "plotly_dark"
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }
    .stApp { background: #10191c; color: #e4eeee; }
    [data-testid="stHeader"] { background: #10191c; }
    [data-testid="stSidebar"] { background: #0b2225; border-right: 1px solid #254044; }
    [data-testid="stSidebar"] * { color: #e4eeee !important; }
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p { color: #9db8b8 !important; }
    h1, h2, h3, p, label, [data-testid="stCaptionContainer"] { color: #e4eeee; }
    [data-testid="stMetric"] { background: #1a2a2e; border: 1px solid #2a4549; padding: 16px; border-radius: 14px; }
    [data-testid="stMetricLabel"] { color: #a9c3c3; }
    [data-testid="stMetricValue"] { color: #f0f7f7; }
    .stButton > button[kind="primary"] { background: #0f9d91; color: #071b1c; border: 0; border-radius: 10px; font-weight: 700; }
    .stButton > button { background: #20383c; color: #e4eeee; border-radius: 10px; border: 1px solid #36565a; }
    [data-testid="stDataFrame"], [data-testid="stPlotlyChart"] { background: #172629; border-radius: 14px; }
    [data-testid="stAlert"] { border-radius: 12px; }
    textarea, input, [data-baseweb="select"] > div { background-color: #1a2a2e !important; color: #e4eeee !important; }
    </style>
    """, unsafe_allow_html=True)
    with st.sidebar:
        st.markdown("## ◈ CROSS-LAYER")
        st.caption("DATABASE BUFFER & MEMORY LAB")
        page = st.radio("WORKSPACE", ["Overview & Benchmark", "SQL Query Lab", "Experiment History"],
                        label_visibility="collapsed")
        st.divider()
        st.caption("POSTGRESQL · OLIST_DB")
    if page == "Overview & Benchmark":
        benchmark_page()
    elif page == "SQL Query Lab":
        query_lab()
    else:
        experiment_history_page()


if __name__ == "__main__":
    main()
