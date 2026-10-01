select metric_date from {{ ref('stg_meta_ads_daily') }} group by 1 having count(*) > 1
