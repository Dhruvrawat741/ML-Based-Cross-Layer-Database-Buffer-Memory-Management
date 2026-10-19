# Page Replacement Benchmark Report

## Experiment setup

- Raw benchmark records: 60
- Frame capacities: 8, 16, 32, 64
- Algorithms: FIFO, LRU, LFU
- Results are based on a synthetic page-reference trace.
- Times are Python simulator measurements, not database latency.

## Results

| Frames | Algorithm | Avg. faults | Hit ratio | Total time (ms) | Replacement time (µs) | Peak traced memory (KB) |
|---:|---|---:|---:|---:|---:|---:|
| 8 | FIFO | 8515.0 | 0.1485 | 11.563 | 2816.252 | 4.28 |
| 8 | LFU | 7741.0 | 0.2259 | 29.508 | 17178.438 | 66.16 |
| 8 | LRU | 8485.0 | 0.1515 | 15.573 | 7303.945 | 71.90 |
| 16 | FIFO | 7278.0 | 0.2722 | 12.966 | 2932.714 | 7.92 |
| 16 | LFU | 5625.0 | 0.4375 | 17.007 | 10971.003 | 52.35 |
| 16 | LRU | 7068.0 | 0.2932 | 19.601 | 9096.205 | 63.67 |
| 32 | FIFO | 5374.0 | 0.4626 | 8.524 | 1744.657 | 15.30 |
| 32 | LFU | 3395.0 | 0.6605 | 14.007 | 9579.976 | 40.16 |
| 32 | LRU | 4818.0 | 0.5182 | 11.615 | 5843.018 | 51.52 |
| 64 | FIFO | 3213.0 | 0.6787 | 5.594 | 927.889 | 27.29 |
| 64 | LFU | 1973.0 | 0.8027 | 12.632 | 9064.892 | 41.91 |
| 64 | LRU | 2441.0 | 0.7559 | 8.362 | 4080.566 | 46.41 |

## Interpretation

- Higher hit ratio and fewer page faults indicate better cache effectiveness for this trace.
- Total simulation time measures the complete Python simulation.
- Replacement time measures the victim-selection section instrumented by the simulator; it is not disk or database I/O latency.
- Peak traced memory measures Python allocations tracked by `tracemalloc`, not total process RAM.
- Timing results are environment-dependent. Use repeated runs and compare averages and standard deviations.
- These are simulated page-replacement results, not direct measurements of PostgreSQL's internal buffer replacement policy.

## Charts

- **Average page faults:** `page_faults_comparison.png`
- **Average hit ratio:** `hit_ratio_comparison.png`
- **Total simulation time:** `total_simulation_time_ms_comparison.png`
- **Replacement decision time:** `replacement_time_us_comparison.png`
- **Peak traced Python memory:** `peak_python_memory_kb_comparison.png`
