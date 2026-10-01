select month_start,identified_customers,first_seen_customers,returning_customers,identified_paid_orders,received_brl
from analytics.fct_customer_activity_monthly where identified_customers>=10 order by 1;

with clients as (
    select customer_key,max(cast(opened_at as date)) as last_seen from analytics.stg_orders
    where order_status='paid' and customer_key is not null group by 1
), recency as (
    select date_diff('day',last_seen,(select max(sale_date) from analytics.fct_daily_sales)) as days_since_last_seen
    from clients
)
select case when days_since_last_seen<=30 then 'Até 30 dias' when days_since_last_seen<=60 then '31-60 dias'
    else 'Mais de 60 dias' end as recency_group,count(*) as customers
from recency group by 1 having count(*)>=5;
