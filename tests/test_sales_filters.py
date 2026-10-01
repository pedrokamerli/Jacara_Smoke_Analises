"""Regressão com a geração real: cada filtro deve alterar SQL e a interface."""
import json
import os
import unittest
from dataclasses import replace
from datetime import date
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest
from jacare_analytics.private_dashboard import SalesFilter, execute_sales, SUMMARY, PRODUCTS

ROOT=Path(__file__).resolve().parents[1]

@unittest.skipUnless((ROOT/"data/current_run.json").exists(),"Geração real ausente")
class SalesFilterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest=json.loads((ROOT/"data/current_run.json").read_text(encoding="utf-8"))
        cls.warehouse=ROOT/cls.manifest["warehouse"]
        cls.full=SalesFilter(date.fromisoformat(cls.manifest["source_start"]),date.fromisoformat(cls.manifest["source_end"]))

    def read(self,filters,sql=SUMMARY):
        return execute_sales(self.warehouse,filters,sql)

    def test_full_period_reconciles_with_approved_manifest(self):
        actual=self.read(self.full).iloc[0]
        self.assertEqual(int(actual.orders),self.manifest["quality"]["paid_orders"])
        self.assertAlmostEqual(float(actual.amount),self.manifest["quality"]["received_brl"],places=2)

    def test_channels_modes_and_weekdays_partition_the_same_orders(self):
        all_count=int(self.read(self.full).iloc[0].orders)
        for field,column in [("channels","source_channel"),("order_types","order_type")]:
            options=self.read(self.full,"select distinct "+column+" as value from selected_orders").value.dropna().tolist()
            parts=[int(self.read(replace(self.full,**{field:(value,)})).iloc[0].orders) for value in options]
            self.assertEqual(sum(parts),all_count)
            if len(parts)>1: self.assertTrue(all(x<all_count for x in parts))
        self.assertEqual(sum(int(self.read(replace(self.full,weekdays=(day,))).iloc[0].orders) for day in range(7)),all_count)

    def test_empty_and_parameterized_selections(self):
        for filters in (replace(self.full,channels=()),replace(self.full,order_types=()),replace(self.full,weekdays=()),replace(self.full,channels=("' OR 1=1 --",))):
            self.assertEqual(int(self.read(filters).iloc[0].orders),0)

    def test_product_totals_change_with_same_date_and_channel_filters(self):
        full=self.read(self.full,PRODUCTS)
        subset=self.read(replace(self.full,start=date(2026,7,1),end=date(2026,7,31),channels=("ifood",)),PRODUCTS)
        self.assertFalse(full.empty)
        self.assertLess(float(subset.units.sum()),float(full.units.sum()))

    def test_widgets_recompute_kpis_and_chart_payload_and_clear(self):
        with patch.dict(os.environ,{"JACARE_PUBLIC_MODE":"false","JACARE_AUTH_MODE":"local","JACARE_READ_ONLY":"true"}):
            app=AppTest.from_file(str(ROOT/"app/streamlit_app.py"),default_timeout=60).run()
            self.assertFalse(app.exception)
            full_orders=next(x.value for x in app.metric if x.label=="Pedidos pagos")
            full_charts=[x.proto.SerializeToString() for x in app.get("vega_lite_chart")]
            self.assertTrue(full_charts)
            app.selectbox(key="sales_preset").set_value("Mês específico").run()
            app.selectbox(key="sales_month").set_value("2026-07").run()
            self.assertFalse(app.exception)
            expected=self.read(replace(self.full,start=date(2026,7,1),end=date(2026,7,31))).iloc[0]
            filtered_orders=next(x.value for x in app.metric if x.label=="Pedidos pagos")
            self.assertEqual(filtered_orders,f"{int(expected.orders):,}".replace(",","."))
            self.assertNotEqual(filtered_orders,full_orders)
            self.assertNotEqual([x.proto.SerializeToString() for x in app.get("vega_lite_chart")],full_charts)
            app.multiselect(key="sales_channels").set_value([]).run()
            self.assertFalse(app.exception)
            self.assertFalse(app.metric)
            self.assertFalse(app.get("vega_lite_chart"))
            next(button for button in app.button if button.label=="Limpar filtros").click().run()
            self.assertFalse(app.exception)
            self.assertEqual(next(x.value for x in app.metric if x.label=="Pedidos pagos"),full_orders)

    def test_channel_type_and_weekday_widgets_match_sql(self):
        with patch.dict(os.environ,{"JACARE_PUBLIC_MODE":"false","JACARE_AUTH_MODE":"local","JACARE_READ_ONLY":"true"}):
            app=AppTest.from_file(str(ROOT/"app/streamlit_app.py"),default_timeout=60).run()
            channels=self.read(self.full,"select source_channel,count(*) as orders from selected_orders group by 1 order by 2 desc").source_channel.tolist()
            channel=channels[0]
            modes=self.read(replace(self.full,channels=(channel,)),"select order_type,count(*) as orders from selected_orders group by 1 order by 2 desc").order_type.tolist()
            mode=modes[0]
            day=int(self.read(replace(self.full,channels=(channel,),order_types=(mode,)),"select (isodow(opened_at)-1) as day,count(*) as orders from selected_orders group by 1 order by 2 desc").iloc[0].day)
            app.multiselect(key="sales_channels").set_value([channel]).run()
            app.multiselect(key="sales_modes").set_value([mode]).run()
            app.multiselect(key="sales_weekdays").set_value([day]).run()
            expected=self.read(replace(self.full,channels=(channel,),order_types=(mode,),weekdays=(day,))).iloc[0]
            self.assertFalse(app.exception)
            self.assertEqual(next(x.value for x in app.metric if x.label=="Pedidos pagos"),f"{int(expected.orders):,}".replace(",","."))

    def test_one_day_is_rendered_with_visible_points(self):
        with patch.dict(os.environ,{"JACARE_PUBLIC_MODE":"false","JACARE_AUTH_MODE":"local","JACARE_READ_ONLY":"true"}):
            app=AppTest.from_file(str(ROOT/"app/streamlit_app.py"),default_timeout=60).run()
            day=self.read(self.full,"select cast(opened_at as date) as day,count(*) as orders from selected_orders group by 1 order by 2 desc").iloc[0].day.date()
            app.selectbox(key="sales_preset").set_value("Personalizado").run()
            app.date_input(key="sales_dates").set_value((day,day)).run()
            self.assertFalse(app.exception)
            specs=[json.loads(x.proto.spec) for x in app.get("vega_lite_chart")]
            daily=next(x for x in specs if x.get("encoding",{}).get("x",{}).get("field")=="day")
            self.assertEqual(daily["mark"]["type"],"line")
            self.assertTrue(daily["mark"]["point"]["filled"])
