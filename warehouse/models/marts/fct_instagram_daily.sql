select
    metric_date,
    metric_key,
    source_label,
    metric_value
from {{ ref('stg_instagram_daily') }}
