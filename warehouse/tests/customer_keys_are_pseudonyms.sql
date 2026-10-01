select order_key from {{ ref('stg_orders') }}
where customer_key is not null and not regexp_full_match(customer_key, 'phone_pos_[a-f0-9]{64}')
