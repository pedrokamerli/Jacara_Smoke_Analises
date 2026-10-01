select date_trunc('month', sale_date)::date as month_start,
    sum(paid_orders) as paid_orders, sum(amount_received_brl) as received_brl,
    sum(amount_received_brl)/nullif(sum(paid_orders),0) as average_ticket_brl,
    count(*) filter(where has_source_records) as observed_days
from analytics.fct_daily_sales group by 1 having sum(paid_orders)>=5 order by 1;
