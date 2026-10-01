select
    cast(metric_date as date) as metric_date,
    cast(spend_brl as decimal(14, 2)) as spend_brl,
    cast(impressions as bigint) as impressions,
    cast(link_clicks as bigint) as link_clicks,
    cast(link_clicks_observed_rows as bigint) as link_clicks_observed_rows,
    cast(link_clicks_missing_rows as bigint) as link_clicks_missing_rows
from {{ local_parquet('meta_ads_daily.parquet') }}
