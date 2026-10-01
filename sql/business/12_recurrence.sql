with customers as (
    select customer_key,count(*) as orders from analytics.stg_orders
    where order_status='paid' and customer_key is not null group by 1
)
select count(*) as identified_customers,count(*) filter(where orders>=2) as recurring_customers,
    (count(*) filter(where orders>=2))::double/nullif(count(*),0) as recurrence_rate,
    sum(orders) as identified_paid_orders
from customers having count(*)>=10;
