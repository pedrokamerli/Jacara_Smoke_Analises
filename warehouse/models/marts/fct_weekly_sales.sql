select
    date_trunc('week', sale_date)::date as week_start,
    sum(paid_orders) as paid_orders,
    sum(order_value_brl)::decimal(14, 2) as order_value_brl,
    sum(amount_received_brl)::decimal(14, 2) as amount_received_brl,
    avg(amount_received_brl)::decimal(12, 2) as average_daily_received_brl,
    count(*) filter (where paid_orders = 0) as days_without_paid_orders,
    count(*) as calendar_days,
    count(*) filter (where has_source_records) as observed_days,
    count(*) filter (where not has_source_records) as missing_days,
    count(*) = 7 as complete_calendar_week
from {{ ref('fct_daily_sales') }}
group by 1
