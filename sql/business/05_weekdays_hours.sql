select 'weekday' as dimension, extract(isodow from sale_date)::integer as value,
    sum(paid_orders) as paid_orders,sum(amount_received_brl) as received_brl
from analytics.fct_daily_sales group by 2 having sum(paid_orders)>=5
union all
select 'hour',hour,sum(paid_orders),sum(received_brl)
from analytics.fct_sales_by_hour group by 2 having sum(paid_orders)>=5
order by dimension,value;
