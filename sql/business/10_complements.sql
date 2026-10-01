select product_name,units_sold,orders_containing_item,item_sales_brl
from analytics.fct_product_performance where item_type='complemento' and orders_containing_item>=5
order by units_sold desc;
