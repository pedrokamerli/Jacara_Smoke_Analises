with appdelivery as (
    select
        order_date,
        sum(orders) filter (where order_status = 'entregue') as delivered_orders,
        sum(items_value_brl) filter (where order_status = 'entregue') as delivered_items_value_brl
    from {{ ref('stg_appdelivery_daily') }}
    group by order_date
), pos_channel as (
    select
        cast(opened_at as date) as order_date,
        count(distinct order_key) as paid_orders,
        sum(items_amount_brl) as pos_items_value_brl
    from {{ ref('stg_orders') }}
    where order_status = 'paid' and source_channel = 'menudino_app_site'
    group by 1
)
select
    coalesce(a.order_date, p.order_date) as order_date,
    coalesce(a.delivered_orders, 0) as appdelivery_delivered_orders,
    coalesce(p.paid_orders, 0) as pos_paid_orders,
    coalesce(a.delivered_orders, 0) - coalesce(p.paid_orders, 0) as order_count_difference,
    coalesce(a.delivered_items_value_brl, 0)::decimal(14,2) as appdelivery_items_value_brl,
    coalesce(p.pos_items_value_brl, 0)::decimal(14,2) as pos_items_value_brl,
    (coalesce(a.delivered_items_value_brl, 0) - coalesce(p.pos_items_value_brl, 0))::decimal(14,2) as items_value_difference_brl
from appdelivery a
full outer join pos_channel p using (order_date)
