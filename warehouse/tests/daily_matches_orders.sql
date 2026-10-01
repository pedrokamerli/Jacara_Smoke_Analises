with daily as (
    select sum(paid_orders) as orders, sum(amount_received_brl) as received from {{ ref('fct_daily_sales') }}
), source as (
    select count(*) as orders, sum(amount_received_brl) as received from {{ ref('stg_orders') }} where order_status = 'paid'
)
select * from daily cross join source where daily.orders <> source.orders or abs(daily.received - source.received) > 0.01
