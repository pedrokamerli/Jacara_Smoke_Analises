with identified as (
    select customer_key, cast(opened_at as date) as sale_date, order_key, amount_received_brl
    from {{ ref('stg_orders') }}
    where order_status = 'paid' and customer_key is not null
), first_seen as (
    select customer_key, min(sale_date) as first_sale_date from identified group by 1
), monthly as (
    select date_trunc('month', sale_date)::date as month_start, customer_key,
        count(*) as orders, sum(amount_received_brl) as received
    from identified group by 1,2
)
select month_start,
    count(*) as identified_customers,
    count(*) filter (where date_trunc('month', first_sale_date)::date = month_start) as first_seen_customers,
    count(*) filter (where date_trunc('month', first_sale_date)::date < month_start) as returning_customers,
    sum(orders) as identified_paid_orders,
    sum(received)::decimal(14,2) as received_brl
from monthly join first_seen using (customer_key) group by 1
