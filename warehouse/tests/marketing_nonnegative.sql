select metric_date from {{ ref('stg_meta_ads_daily') }} where spend_brl < 0 or impressions < 0 or link_clicks < 0
