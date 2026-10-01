with source as (
    select *
    from {{ local_parquet('orders.parquet') }}
)

select
    cast(order_key as bigint) as order_key,
    cast(opened_at as timestamp) as opened_at,
    cast(closed_at as timestamp) as closed_at,
    cast(order_status as varchar) as order_status,
    cast(order_type as varchar) as order_type,
    cast(source_channel as varchar) as source_channel,
    cast(delivery_type as varchar) as delivery_type,
    cast(items_amount_brl as decimal(12, 2)) as items_amount_brl,
    cast(service_fee_brl as decimal(12, 2)) as service_fee_brl,
    cast(delivery_fee_brl as decimal(12, 2)) as delivery_fee_brl,
    cast(order_total_brl as decimal(12, 2)) as order_total_brl,
    cast(amount_received_brl as decimal(12, 2)) as amount_received_brl,
    cast(customer_key as varchar) as customer_key
from source
