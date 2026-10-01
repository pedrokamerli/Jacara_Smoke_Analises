select cast(order_date as date) as order_date, cast(order_status as varchar) as order_status,
    cast(orders as bigint) as orders, cast(items_value_brl as decimal(14,2)) as items_value_brl,
    cast(customer_paid_brl as decimal(14,2)) as customer_paid_brl,
    cast(delivery_fee_brl as decimal(14,2)) as delivery_fee_brl
from {{ local_parquet('ifood_daily.parquet') }}
