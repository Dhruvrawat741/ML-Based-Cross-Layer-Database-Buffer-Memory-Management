import csv
import hashlib
import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

import sqlparse

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parent

SQL_FILE = PROJECT / "experiments" / "olist_workload.sql"
OUTPUT_DIR = ROOT / "data"
OUTPUT_FILE = OUTPUT_DIR / "olist_2000_records.csv"

TARGET_RECORDS = 2000
DATABASE = "olist_db"

FIELDS = [
    "record_id", "timestamp_utc", "workload_run", "query_number",
    "query_id", "query",
    "execution_time_ms", "planning_time_ms",
    "shared_hit_blocks", "shared_read_blocks",
    "shared_dirtied_blocks", "shared_written_blocks",
    "temp_read_blocks", "temp_written_blocks",
    "plan_rows", "plan_width",
    "cache_total_buffers", "cache_used_buffers",
    "cache_dirty_buffers", "cache_pinned_buffers",
]


def psql(sql):
    result = subprocess.run(
        [
            "sudo", "-u", "postgres",
            "psql", "-X", "-qAt",
            "-v", "ON_ERROR_STOP=1",
            "-d", DATABASE,
            "-c", sql,
        ],
        capture_output=True,
        text=True,
        timeout=180,
    )

    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip())

    return result.stdout.strip()


def get_cache_snapshot():
    sql = """
    SELECT json_build_object(
        'total', count(*),
        'used', count(*) FILTER (WHERE relfilenode IS NOT NULL),
        'dirty', count(*) FILTER (WHERE isdirty),
        'pinned', count(*) FILTER (WHERE pinning_backends > 0)
    )::text
    FROM pg_buffercache;
    """
    return json.loads(psql(sql))



def load_queries():
    if not SQL_FILE.exists():
        raise FileNotFoundError(f"Workload not found: {SQL_FILE}")

    source = SQL_FILE.read_text(encoding="utf-8")

    # Remove psql meta-commands such as \timing on.
    source = "\n".join(
        line for line in source.splitlines()
        if not line.lstrip().startswith("\\")
    )

    statements = []
    for statement in sqlparse.split(source):
        query = sqlparse.format(
            statement,
            strip_comments=True
        ).strip()

        if not query:
            continue

        parsed = sqlparse.parse(query)
        if not parsed or parsed[0].get_type() != "SELECT":
            raise ValueError(
                f"Unsupported statement in workload: {query[:100]}"
            )

        statements.append(query)

    if not statements:
        raise ValueError("No SELECT queries found.")

    print(f"Validated {len(statements)} SELECT queries.")
    return statements


def run_query(query):
    explain_sql = (
        "EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) " + query
    )
    output = psql(explain_sql)
    document = json.loads(output)[0]

    plan = document["Plan"]

    return {
        "execution_time_ms": document.get("Execution Time", 0),
        "planning_time_ms": document.get("Planning Time", 0),
        "shared_hit_blocks": plan.get("Shared Hit Blocks", 0),
        "shared_read_blocks": plan.get("Shared Read Blocks", 0),
        "shared_dirtied_blocks": plan.get("Shared Dirtied Blocks", 0),
        "shared_written_blocks": plan.get("Shared Written Blocks", 0),
        "temp_read_blocks": plan.get("Temp Read Blocks", 0),
        "temp_written_blocks": plan.get("Temp Written Blocks", 0),
        "plan_rows": plan.get("Plan Rows", 0),
        "plan_width": plan.get("Plan Width", 0),
    }


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if OUTPUT_FILE.exists():
        raise FileExistsError(
            f"{OUTPUT_FILE} already exists. "
            "Rename or back it up before starting a new collection."
        )

    queries = load_queries()

    print(f"Loaded {len(queries)} real Olist queries.")
    print(f"Target: {TARGET_RECORDS:,} successful records.")
    print("Starting collection...\n")

    count = 0
    start = time.time()

    with OUTPUT_FILE.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDS)
        writer.writeheader()
        file.flush()

        while count < TARGET_RECORDS:
            workload_run = count // len(queries) + 1

            for query_number, query in enumerate(queries, 1):
                if count >= TARGET_RECORDS:
                    break

                metrics = run_query(query)
                cache = get_cache_snapshot()

                count += 1
                query_id = hashlib.sha256(
                    " ".join(query.split()).encode()
                ).hexdigest()[:16]

                row = {
                    "record_id": count,
                    "timestamp_utc": datetime.now(
                        timezone.utc
                    ).isoformat(),
                    "workload_run": workload_run,
                    "query_number": query_number,
                    "query_id": query_id,
                    "query": " ".join(query.split())[:1000],
                    **metrics,
                    "cache_total_buffers": cache["total"],
                    "cache_used_buffers": cache["used"],
                    "cache_dirty_buffers": cache["dirty"],
                    "cache_pinned_buffers": cache["pinned"],
                }

                writer.writerow(row)
                file.flush()

                if count % 25 == 0 or count == 1:
                    elapsed = time.time() - start
                    rate = count / elapsed if elapsed else 0
                    print(
                        f"Collected {count:4}/{TARGET_RECORDS} | "
                        f"Run {workload_run} | "
                        f"Latest query time: "
                        f"{metrics['execution_time_ms']:.2f} ms | "
                        f"Rate: {rate:.2f} records/sec",
                        flush=True,
                    )

    elapsed = time.time() - start

    print("\n======================================")
    print("COLLECTION COMPLETED")
    print("======================================")
    print(f"Records collected: {count}")
    print(f"Time taken: {elapsed / 60:.2f} minutes")
    print(f"Output: {OUTPUT_FILE}")
    print("======================================")


if __name__ == "__main__":
    main()
