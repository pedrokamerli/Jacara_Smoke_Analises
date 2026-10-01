select order_key from {{ ref('stg_orders') }} group by 1 having count(*) > 1 or order_key is null
