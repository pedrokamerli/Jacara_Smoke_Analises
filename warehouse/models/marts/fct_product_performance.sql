select
    coalesce(item.product_name, 'unknown') as product_name,
    coalesce(item.product_category, 'uncategorized') as product_category,
    coalesce(item.item_type, 'unknown') as item_type,
    sum(item.quantity)::decimal(14, 3) as units_sold,
    count(distinct item.order_key) as orders_containing_item,
    sum(item.line_total_brl)::decimal(14, 2) as item_sales_brl
from {{ ref('stg_items') }} as item
inner join {{ ref('stg_orders') }} as orders
    on item.order_key = orders.order_key
where orders.order_status = 'paid'
group by 1, 2, 3
