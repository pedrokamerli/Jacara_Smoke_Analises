select metric_date from {{ ref('fct_marketing_daily') }}
where link_clicks_missing_rows > 0 and (cpc_brl is not null or link_ctr is not null)
