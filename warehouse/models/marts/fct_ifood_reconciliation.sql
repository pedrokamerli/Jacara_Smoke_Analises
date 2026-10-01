with external as (
    select order_date, sum(orders) as reported_orders, sum(customer_paid_brl) as customer_paid_brl
    from {{ ref('stg_ifood_daily') }} where order_status = 'concluido' group by 1
), pdv as (
    select cast(opened_at as date) as order_date, count(*) as pdv_paid_orders,
        sum(amount_received_brl) as pdv_received_brl
    from {{ ref('stg_orders') }} where order_status = 'paid' and source_channel = 'ifood' group by 1
)
select external.*, pdv.pdv_paid_orders, pdv.pdv_received_brl,
    external.reported_orders - pdv.pdv_paid_orders as order_difference
from external left join pdv using(order_date)
