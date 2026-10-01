with paid_orders as (
    select
        cast(opened_at as date) as sale_date,
        order_key,
        order_total_brl,
        amount_received_brl,
        items_amount_brl,
        delivery_fee_brl,
        source_channel
    from {{ ref('stg_orders') }}
    where order_status = 'paid'
),
daily as (
    select
        sale_date,
        count(distinct order_key) as paid_orders,
        sum(order_total_brl) as order_value_brl,
        sum(amount_received_brl) as amount_received_brl,
        sum(items_amount_brl) as items_amount_brl,
        sum(delivery_fee_brl) as delivery_fee_brl,
        count(distinct source_channel) as active_channels
    from paid_orders
    group by sale_date
),
calendar as (
    select cast(day_value as date) as sale_date
    from generate_series(
        (select min(cast(opened_at as date)) from {{ ref('stg_orders') }}),
        (select max(cast(opened_at as date)) from {{ ref('stg_orders') }}),
        interval 1 day
    ) as dates(day_value)
),
captured_dates as (
    select distinct cast(opened_at as date) as sale_date from {{ ref('stg_orders') }}
)

select
    calendar.sale_date,
    captured_dates.sale_date is not null as has_source_records,
    case when captured_dates.sale_date is not null then coalesce(daily.paid_orders, 0) end as paid_orders,
    case when captured_dates.sale_date is not null then coalesce(daily.order_value_brl, 0) end::decimal(14, 2) as order_value_brl,
    case when captured_dates.sale_date is not null then coalesce(daily.amount_received_brl, 0) end::decimal(14, 2) as amount_received_brl,
    case when captured_dates.sale_date is not null then coalesce(daily.items_amount_brl, 0) end::decimal(14, 2) as items_amount_brl,
    case when captured_dates.sale_date is not null then coalesce(daily.delivery_fee_brl, 0) end::decimal(14, 2) as delivery_fee_brl,
    daily.active_channels
from calendar
left join daily using (sale_date)
left join captured_dates using (sale_date)
