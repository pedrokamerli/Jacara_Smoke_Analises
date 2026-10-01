select * from (
    select week_start,paid_orders,amount_received_brl,observed_days,missing_days,
        rank() over(order by amount_received_brl desc) as highest_value_rank,
        rank() over(order by amount_received_brl asc) as lowest_value_rank,
        rank() over(order by paid_orders desc) as highest_volume_rank,
        rank() over(order by paid_orders asc) as lowest_volume_rank
    from analytics.fct_weekly_sales where complete_calendar_week and paid_orders>=5
) where highest_value_rank=1 or lowest_value_rank=1 or highest_volume_rank=1 or lowest_volume_rank=1
order by week_start;
