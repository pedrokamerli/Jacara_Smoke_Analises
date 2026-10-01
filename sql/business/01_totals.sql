select min(sale_date) as first_date, max(sale_date) as last_date,
    sum(paid_orders) as paid_orders, sum(amount_received_brl) as received_brl,
    count(*) filter(where has_source_records) as observed_days,
    count(*) filter(where not has_source_records) as missing_days
from analytics.fct_daily_sales;
