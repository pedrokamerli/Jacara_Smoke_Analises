select cast(opened_at as date) as sale_date, extract(hour from opened_at)::integer as hour,
    count(*) as paid_orders, sum(amount_received_brl)::decimal(14,2) as received_brl
from {{ ref('stg_orders') }} where order_status = 'paid' group by 1,2
