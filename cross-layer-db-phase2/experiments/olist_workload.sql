
\timing on

-- Query 1: Count orders by status
SELECT order_status, COUNT(*)
FROM orders
GROUP BY order_status;

-- Query 2: Count orders within a date range
SELECT COUNT(*)
FROM orders
WHERE order_purchase_timestamp >= '2018-01-01'
  AND order_purchase_timestamp < '2018-04-01';

-- Query 3: Top 10 product categories by revenue
SELECT
    p.product_category_name,
    SUM(oi.price) AS revenue
FROM order_items oi
JOIN products p ON p.product_id = oi.product_id
GROUP BY p.product_category_name
ORDER BY revenue DESC
LIMIT 10;

-- Query 4: Revenue by order status
SELECT
    o.order_status,
    COUNT(*) AS item_count,
    SUM(oi.price) AS total_revenue
FROM orders o
JOIN order_items oi ON o.order_id = oi.order_id
GROUP BY o.order_status;

-- Query 5: Top 10 customers by number of orders
SELECT
    customer_id,
    COUNT(*) AS total_orders
FROM orders
GROUP BY customer_id
ORDER BY total_orders DESC
LIMIT 10;

-- Query 6: Average order-item price by product
SELECT
    product_id,
    AVG(price) AS average_price,
    COUNT(*) AS item_count
FROM order_items
GROUP BY product_id
ORDER BY average_price DESC
LIMIT 10;

-- Query 7: Number of orders by customer state
SELECT
    c.customer_state,
    COUNT(*) AS total_orders
FROM customers c
JOIN orders o ON o.customer_id = c.customer_id
GROUP BY c.customer_state
ORDER BY total_orders DESC;

-- Query 8: Payment value by payment type
SELECT
    payment_type,
    COUNT(*) AS payment_count,
    SUM(payment_value) AS total_payment
FROM order_payments
GROUP BY payment_type
ORDER BY total_payment DESC;

-- Query 9: Review score distribution
SELECT
    review_score,
    COUNT(*) AS total_reviews
FROM order_reviews
GROUP BY review_score
ORDER BY review_score;

-- Query 10: Monthly order counts
SELECT
    DATE_TRUNC('month', order_purchase_timestamp) AS order_month,
    COUNT(*) AS total_orders
FROM orders
WHERE order_purchase_timestamp IS NOT NULL
GROUP BY DATE_TRUNC('month', order_purchase_timestamp)
ORDER BY order_month;
