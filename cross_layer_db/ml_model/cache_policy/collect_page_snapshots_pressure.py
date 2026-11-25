import csv
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
INPUT = ROOT / "data" / "olist_2000_records.csv"
OUTPUT = ROOT / "data" / "olist_page_snapshots_pressure.csv"
DATABASE = "olist_db"


def psql(sql):
    result = subprocess.run(
        ["sudo", "-u", "postgres", "psql", "-X", "-qAt",
         "-v", "ON_ERROR_STOP=1", "-d", DATABASE, "-c", sql],
        capture_output=True, text=True, timeout=180
    )
    if result.returncode:
        raise RuntimeError(result.stderr.strip())
    return result.stdout.strip()


def main():
    with INPUT.open(newline="", encoding="utf-8") as f:
        queries = list(csv.DictReader(f))

    if len(queries) != 2000:
        raise ValueError(f"Expected 2000 records, got {len(queries)}")

    snapshot_sql = """
    SELECT COALESCE(json_agg(json_build_object(
        'tablespace', reltablespace,
        'database', reldatabase,
        'relation', relfilenode,
        'fork', relforknumber,
        'block', relblocknumber,
        'usage_count', usagecount,
        'dirty', isdirty,
        'pinned', pinning_backends
    )), '[]'::json)::text
    FROM pg_buffercache
    WHERE reldatabase = (
        SELECT oid FROM pg_database WHERE datname = current_database()
    )
    AND relfilenode IS NOT NULL;
    """

    fields = [
        "snapshot_id", "record_id", "query_id", "timestamp_utc",
        "page_id", "tablespace", "database", "relation",
        "fork", "block", "usage_count", "dirty", "pinned"
    ]

    with OUTPUT.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()

        for i, record in enumerate(queries, 1):
            psql(
                "EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) "
                + record["query"]
            )

            pages = json.loads(psql(snapshot_sql))
            timestamp = datetime.now(timezone.utc).isoformat()

            for page in pages:
                page_id = ":".join(str(page[k]) for k in (
                    "tablespace", "database", "relation", "fork", "block"
                ))
                writer.writerow({
                    "snapshot_id": i,
                    "record_id": record["record_id"],
                    "query_id": record["query_id"],
                    "timestamp_utc": timestamp,
                    "page_id": page_id,
                    **page
                })

            f.flush()

            if i % 25 == 0 or i == 1:
                print(
                    f"Captured {i}/2000 snapshots | "
                    f"{len(pages)} resident pages",
                    flush=True
                )

    print("COMPLETED:", OUTPUT)


if __name__ == "__main__":
    main()
