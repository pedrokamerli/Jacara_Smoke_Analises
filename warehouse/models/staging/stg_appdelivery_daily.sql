select
    cast(order_date as date) as order_date,
    cast(delivery_type as varchar) as delivery_type,
    cast(order_status as varchar) as order_status,
    cast(orders as bigint) as orders,
    cast(items_value_brl as decimal(14, 2)) as items_value_brl,
    cast(delivery_fee_brl as decimal(14, 2)) as delivery_fee_brl
from {{ local_parquet('appdelivery_daily.parquet') }}
