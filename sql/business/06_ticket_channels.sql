select source_channel,count(*) as paid_orders,sum(amount_received_brl) as received_brl,
    avg(amount_received_brl) as average_ticket_brl
from analytics.stg_orders where order_status='paid'
group by 1 having count(*)>=5 order by received_brl desc;
