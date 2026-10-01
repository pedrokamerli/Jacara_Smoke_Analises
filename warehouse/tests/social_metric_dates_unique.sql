select metric_key, metric_date from {{ ref('stg_instagram_daily') }} group by 1,2 having count(*) > 1
