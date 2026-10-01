with customers as (
    select customer_key,count(*) as orders,sum(amount_received_brl) as received
    from analytics.stg_orders where order_status='paid' and customer_key is not null group by 1
), groups as (
    select case when orders=1 then '1 pedido' when orders<=3 then '2-3 pedidos'
        when orders<=7 then '4-7 pedidos' else '8+ pedidos' end as frequency_group,orders,received
    from customers
)
select frequency_group,count(*) as customers,sum(orders) as orders,sum(received) as received_brl,
    avg(received) as average_received_per_customer
from groups group by 1 having count(*)>=5 order by average_received_per_customer desc;
