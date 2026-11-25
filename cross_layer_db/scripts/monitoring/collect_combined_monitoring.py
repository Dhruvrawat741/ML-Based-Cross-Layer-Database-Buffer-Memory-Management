
import argparse
import csv
import getpass
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import psycopg
import psutil


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "combined_monitoring"

QUERIES = {
    "buffer_snapshots.csv": """
        SELECT
            bufferid, reltablespace, reldatabase, relfilenode,
            relforknumber, relblocknumber, usagecount,
            isdirty, pinning_backends
        FROM pg_buffercache
        WHERE reldatabase = (
            SELECT oid FROM pg_database
            WHERE datname = current_database()
        )
    """,

    "query_statistics.csv": """
        SELECT
            queryid, calls, rows,
            shared_blks_hit, shared_blks_read,
            shared_blks_dirtied, shared_blks_written,
            total_exec_time, mean_exec_time, query
        FROM pg_stat_statements
        WHERE dbid = (
            SELECT oid FROM pg_database
            WHERE datname = current_database()
        )
    """,

    "io_statistics.csv": """
        SELECT
            backend_type, object, context,
            reads, hits, evictions, reuses,
            writes, writebacks, extends, fsyncs
        FROM pg_stat_io
    """
}


def write_csv(filename, rows, columns):
    path = OUT / filename
    exists = path.exists() and path.stat().st_size > 0

    with path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=["observed_at_utc"] + columns
        )

        if not exists:
            writer.writeheader()

        timestamp = datetime.now(timezone.utc).isoformat()

        for row in rows:
            writer.writerow({
                "observed_at_utc": timestamp,
                **dict(zip(columns, row))
            })


def collect_query(conn, filename, sql):
    with conn.cursor() as cur:
        cur.execute(sql)
        rows = cur.fetchall()
        columns = [desc.name for desc in cur.description]

    write_csv(filename, rows, columns)
    return len(rows)


def collect_os():
    disk = psutil.disk_io_counters()
    memory = psutil.virtual_memory()

    return {
        "cpu_percent": psutil.cpu_percent(),
        "memory_percent": memory.percent,
        "memory_used_bytes": memory.used,
        "disk_read_bytes": disk.read_bytes if disk else None,
        "disk_write_bytes": disk.write_bytes if disk else None,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--duration", type=int, default=120)
    parser.add_argument("--interval", type=int, default=5)
    args = parser.parse_args()

    if args.duration < 1 or args.interval < 1:
        parser.error("Duration and interval must be positive.")

    OUT.mkdir(parents=True, exist_ok=True)

    password = getpass.getpass("PostgreSQL password: ")

    print("Connecting to PostgreSQL...")

    with psycopg.connect(
        host="localhost",
        port=5432,
        dbname="olist_db",
        user="experiment_user",
        password=password,
        connect_timeout=10
    ) as conn:

        metadata = {
            "database": "olist_db",
            "postgresql_host": "localhost",
            "collection_started_utc":
                datetime.now(timezone.utc).isoformat(),
            "interval_seconds": args.interval,
            "duration_seconds": args.duration,
            "sources": list(QUERIES.keys()) + ["os_metrics.csv"]
        }

        metadata_path = OUT / "collection_metadata.json"

        with metadata_path.open("w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)

        print("Collection started.")
        print(f"Output: {OUT}")

        start = time.monotonic()
        sample = 0

        while time.monotonic() - start < args.duration:
            sample_start = time.monotonic()

            try:
                for filename, sql in QUERIES.items():
                    count = collect_query(conn, filename, sql)
                    print(f"{filename}: {count} rows")

                os_metrics = collect_os()
                write_csv(
                    "os_metrics.csv",
                    [list(os_metrics.values())],
                    list(os_metrics.keys())
                )

                sample += 1
                print(f"Sample {sample} completed.")

            except Exception as exc:
                print(f"Collection error: {exc}")
                conn.rollback()

            elapsed = time.monotonic() - sample_start
            time.sleep(max(0, args.interval - elapsed))

        metadata["collection_finished_utc"] = (
            datetime.now(timezone.utc).isoformat()
        )
        metadata["samples_completed"] = sample

        with metadata_path.open("w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)

    print(f"Collection finished. Samples: {sample}")


if __name__ == "__main__":
    main()

