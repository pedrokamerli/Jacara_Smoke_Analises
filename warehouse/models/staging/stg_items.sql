with source as (
    select *
    from {{ local_parquet('items.parquet') }}
)

select
    cast(order_key as bigint) as order_key,
    cast(sold_at as timestamp) as sold_at,
    cast(quantity as decimal(12, 3)) as quantity,
    cast(unit_price_brl as decimal(12, 2)) as unit_price_brl,
    cast(line_total_brl as decimal(12, 2)) as line_total_brl,
    cast(item_type as varchar) as item_type,
    cast(product_name as varchar) as product_name,
    cast(product_type as varchar) as product_type,
    cast(product_category as varchar) as product_category,
    cast(order_type as varchar) as order_type,
    cast(order_status as varchar) as order_status
from source
