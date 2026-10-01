select
    cast(metric_date as date) as metric_date,
    cast(metric_key as varchar) as metric_key,
    cast(source_label as varchar) as source_label,
    cast(metric_value as double) as metric_value
from {{ local_parquet('instagram_daily.parquet') }}
