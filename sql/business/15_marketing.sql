select metric_key,count(*) as observations,min(metric_date) as first_date,max(metric_date) as last_date,
    arg_min(metric_value,metric_date) as first_value,arg_max(metric_value,metric_date) as last_value
from analytics.fct_instagram_daily group by 1;

select sum(spend_brl) as spend_brl,sum(impressions) as impressions,sum(link_clicks) as link_clicks,
    sum(link_clicks_missing_rows) as link_clicks_missing_rows,
    case when sum(link_clicks_missing_rows)=0 then sum(spend_brl)/nullif(sum(link_clicks),0) end as cpc_brl,
    case when sum(link_clicks_missing_rows)=0 then sum(link_clicks)::double/nullif(sum(impressions),0) end as link_ctr
from analytics.fct_marketing_daily;

select count(*) as paired_dates,corr(spend_brl,amount_received_brl) as descriptive_correlation
from analytics.fct_marketing_daily where paid_orders>=5 and amount_received_brl is not null
having count(*)>=10;
