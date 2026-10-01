select sale_date from {{ ref('fct_daily_sales') }}
where not has_source_records and (paid_orders is not null or amount_received_brl is not null)
