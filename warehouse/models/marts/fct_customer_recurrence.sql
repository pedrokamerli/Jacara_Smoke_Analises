with customer_orders as (
    select
        customer_key,
        count(distinct order_key) as paid_orders,
        sum(amount_received_brl)::decimal(14, 2) as total_received_brl
    from {{ ref('stg_orders') }}
    where order_status = 'paid'
      and customer_key is not null
      and customer_key <> ''
    group by customer_key
)

select
    count(*) as identified_customers,
    count(*) filter (where paid_orders >= 2) as recurring_customers,
    coalesce(
        cast(count(*) filter (where paid_orders >= 2) as decimal(12, 4))
        / nullif(count(*), 0),
        0
    ) as recurrence_rate,
    coalesce(sum(total_received_brl), 0)::decimal(14, 2) as received_from_identified_customers_brl
from customer_orders
