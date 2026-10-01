select items.order_key from {{ ref('stg_items') }} items
left join {{ ref('stg_orders') }} orders using (order_key)
where orders.order_key is null
