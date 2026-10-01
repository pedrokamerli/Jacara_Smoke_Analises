select
    ads.*,
    case when ads.link_clicks_missing_rows = 0 then ads.spend_brl / nullif(ads.link_clicks, 0) end as cpc_brl,
    case when ads.link_clicks_missing_rows = 0 then ads.link_clicks::double / nullif(ads.impressions, 0) end as link_ctr,
    sales.paid_orders,
    sales.amount_received_brl
from {{ ref('stg_meta_ads_daily') }} as ads
left join {{ ref('fct_daily_sales') }} as sales on ads.metric_date = sales.sale_date
