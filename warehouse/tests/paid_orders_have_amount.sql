select order_key from {{ ref('stg_orders') }} where order_status = 'paid' and amount_received_brl is null
