
import csv
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import psycopg

DB_CONFIG = {
    "host": "localhost",
    "dbname": "olist_db",
    "user": "experiment_user",
    "password": os.environ.get("PGPASSWORD"),
}

OUTPUT_DIR = Path("data/OS_result")
OUTPUT_FILE = OUTPUT_DIR / "query_metrics.csv"

QUERIES = [
    (
        1,
        "Count orders by status",
        """
        SELECT order_status, COUNT(*)
        FROM orders
        GROUP BY order_status
        """,
    ),
    (
        2,
        "Count orders within date range",
        """
        SELECT COUNT(*)
        FROM orders
        WHERE order_purchase_timestamp >= '2018-01-01'
          AND order_purchase_timestamp < '2018-04-01'
        """,
    ),
    (
        3,
        "Top product categories by revenue",
        """
        SELECT p.product_category_name, SUM(oi.price) AS revenue
        FROM order_items oi
        JOIN products p ON p.product_id = oi.product_id
        GROUP BY p.product_category_name
        ORDER BY revenue DESC
        LIMIT 10
        """,
    ),
    (
        4,
        "Revenue by order status",
        """
        SELECT o.order_status, COUNT(*) AS item_count,
               SUM(oi.price) AS total_revenue
        FROM orders o
        JOIN order_items oi ON o.order_id = oi.order_id
        GROUP BY o.order_status
        """,
    ),
    (
        5,
        "Top customers by number of orders",
        """
        SELECT customer_id, COUNT(*) AS total_orders
        FROM orders
        GROUP BY customer_id
        ORDER BY total_orders DESC
        LIMIT 10
        """,
    ),
    (
        6,
        "Average order-item price by product",
        """
        SELECT product_id, AVG(price) AS average_price,
               COUNT(*) AS item_count
        FROM order_items
        GROUP BY product_id
        ORDER BY average_price DESC
        LIMIT 10
        """,
    ),
    (
        7,
        "Orders by customer state",
        """
        SELECT c.customer_state, COUNT(*) AS total_orders
        FROM customers c
        JOIN orders o ON o.customer_id = c.customer_id
        GROUP BY c.customer_state
        ORDER BY total_orders DESC
        """,
    ),
    (
        8,
        "Payment value by payment type",
        """
        SELECT payment_type, COUNT(*) AS payment_count,
               SUM(payment_value) AS total_payment
        FROM order_payments
        GROUP BY payment_type
        ORDER BY total_payment DESC
        """,
    ),
    (
        9,
        "Review score distribution",
        """
        SELECT review_score, COUNT(*) AS total_reviews
        FROM order_reviews
        GROUP BY review_score
        ORDER BY review_score
        """,
    ),
    (
        10,
        "Monthly order counts",
        """
        SELECT DATE_TRUNC('month', order_purchase_timestamp)
                   AS order_month,
               COUNT(*) AS total_orders
        FROM orders
        WHERE order_purchase_timestamp IS NOT NULL
        GROUP BY DATE_TRUNC('month', order_purchase_timestamp)
        ORDER BY order_month
        """,
    ),
]

FIELDS = [
    "run_id",
    "query_id",
    "query_name",
    "timestamp_utc",
    "execution_time_ms",
    "rows_returned",
    "shared_hit_blocks",
    "shared_read_blocks",
    "shared_dirtied_blocks",
    "shared_written_blocks",
    "local_hit_blocks",
    "local_read_blocks",
    "temp_read_blocks",
    "temp_written_blocks",
    "planning_time_ms",
    "execution_time_explain_ms",
]


def parse_explain(lines):
    """Extract EXPLAIN ANALYZE metrics from PostgreSQL JSON output."""
    plan = lines[0][0]

    # PostgreSQL JSON EXPLAIN output is a list containing one plan object.
    if isinstance(plan, list):
        plan = plan[0]

    root = plan["Plan"]
    root = plan["Plan"]
    return {
        "rows_returned": root.get("Actual Rows", 0),
        "shared_hit_blocks": root.get("Shared Hit Blocks", 0),
        "shared_read_blocks": root.get("Shared Read Blocks", 0),
        "shared_dirtied_blocks": root.get("Shared Dirtied Blocks", 0),
        "shared_written_blocks": root.get("Shared Written Blocks", 0),
        "local_hit_blocks": root.get("Local Hit Blocks", 0),
        "local_read_blocks": root.get("Local Read Blocks", 0),
        "temp_read_blocks": root.get("Temp Read Blocks", 0),
        "temp_written_blocks": root.get("Temp Written Blocks", 0),
        "planning_time_ms": plan.get("Planning Time", 0),
        "execution_time_explain_ms": plan.get("Execution Time", 0),
    }


def main():
    if not DB_CONFIG["password"]:
        raise SystemExit(
            "Set PGPASSWORD first, then run this script."
        )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    file_exists = OUTPUT_FILE.exists() and OUTPUT_FILE.stat().st_size > 0

    with psycopg.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur, OUTPUT_FILE.open(
            "a", newline="", encoding="utf-8"
        ) as output:
            writer = csv.DictWriter(output, fieldnames=FIELDS)

            if not file_exists:
                writer.writeheader()

            for query_id, query_name, sql in QUERIES:
                explain_sql = (
                    "EXPLAIN (ANALYZE, BUFFERS, TIMING, FORMAT JSON) "
                    + sql
                )

                start = time.perf_counter()
                cur.execute(explain_sql)
                explain_result = cur.fetchall()
                wall_time_ms = (time.perf_counter() - start) * 1000

                metrics = parse_explain(explain_result)
                row = {
                    "run_id": run_id,
                    "query_id": query_id,
                    "query_name": query_name,
                    "timestamp_utc": datetime.now(
                        timezone.utc
                    ).isoformat(),
                    "execution_time_ms": round(wall_time_ms, 3),
                    **metrics,
                }

                writer.writerow(row)
                output.flush()

                print(
                    f"Query {query_id}: {query_name} | "
                    f"execution={metrics['execution_time_explain_ms']:.3f} ms | "
                    f"shared hits={metrics['shared_hit_blocks']} | "
                    f"shared reads={metrics['shared_read_blocks']}"
                )

    print(f"\nSaved query metrics to: {OUTPUT_FILE}")
    print(f"Run ID: {run_id}")


if __name__ == "__main__":
    main()
