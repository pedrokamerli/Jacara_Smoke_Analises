select source_channel,count(*) as paid_orders,sum(amount_received_brl) as received_brl
from analytics.stg_orders where order_status='paid' and source_channel in ('ifood','menudino_app_site')
group by 1 having count(*)>=5;

select count(*) as comparable_days,count(*) filter(where order_count_difference=0) as same_count_days,
    sum(items_value_difference_brl) as items_difference_brl
from analytics.fct_appdelivery_reconciliation
where appdelivery_delivered_orders>0 and pos_paid_orders>0;

select orders,covered_days,first_order_date,last_order_date,sales_revenue_brl,shop_revenue_brl,
    commission_expense_brl,payment_channel_fee_brl,orders_with_both_timestamps,
    late_preparation_orders,average_prep_minutes,average_acceptance_seconds,average_finalization_seconds
from analytics.fct_food99_summary;

select count(*) as reported_dates,sum(reported_orders) as reported_orders,sum(pdv_paid_orders) as pdv_paid_orders,
    count(*) filter(where order_difference=0) as matching_dates
from analytics.fct_ifood_reconciliation;

select date_trunc('month',order_date)::date as month_start,delivery_type,order_status,
    sum(orders) as orders,sum(items_value_brl) as items_value_brl,sum(delivery_fee_brl) as delivery_fee_brl,
    min(order_date) as first_date,max(order_date) as last_date
from analytics.stg_appdelivery_daily
group by 1,2,3 having sum(orders)>=5 order by 1,2,3;
