select product_name,product_category,item_type,units_sold,orders_containing_item,item_sales_brl
from analytics.fct_product_performance where orders_containing_item>=5
order by item_sales_brl desc limit 20;
