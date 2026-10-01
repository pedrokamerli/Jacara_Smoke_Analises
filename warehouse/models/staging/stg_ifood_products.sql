select cast(product_name as varchar) as product_name, cast(visits as bigint) as visits,
    cast(orders as bigint) as orders, cast(units_sold as double) as units_sold,
    cast(reported_value_brl as decimal(14,2)) as reported_value_brl
from {{ local_parquet('ifood_products.parquet') }}
