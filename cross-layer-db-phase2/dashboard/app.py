from __future__ import annotations
import json, time, tracemalloc
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

def main():
    st.set_page_config(page_title="Cross-Layer Cache Lab", page_icon="🧠", layout="wide")
    st.title("ML-Based Cross-Layer Database Buffer & Memory Management")
    st.caption("Interactive, reproducible comparison of FIFO, LRU, LFU and ML cache replacement.")
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
        st.session_state["result"] = result
        st.session_state["meta"] = {"label":label,"csv":str(csv_path),"json":str(json_path),"training":training_ms}
        st.success(f"Completed. Saved CSV and JSON in {RESULTS}")
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
            st.plotly_chart(px.bar(result,x="policy",y="hit_ratio_pct",color="policy",title="Cache hit ratio (%)",text_auto=".2f"),use_container_width=True)
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

if __name__ == "__main__":
    main()
