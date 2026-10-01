select
    coalesce(source_channel, 'unknown') as source_channel,
    count(distinct order_key) as paid_orders,
    sum(order_total_brl)::decimal(14, 2) as order_value_brl,
    sum(amount_received_brl)::decimal(14, 2) as amount_received_brl,
    avg(amount_received_brl)::decimal(12, 2) as average_ticket_received_brl,
    sum(delivery_fee_brl)::decimal(14, 2) as delivery_fees_brl
from {{ ref('stg_orders') }}
where order_status = 'paid'
group by 1
