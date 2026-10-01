"""Regressão do dashboard usando somente a geração real local, sem fixtures fictícias.

Executar: python -m unittest discover -s tests -v
"""

import json
import os
import unittest
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from jacare_analytics.dashboard_story import QUESTION_TITLES, INTERPRETATIONS, answer_summary
from jacare_analytics.forecast_backtest import MODEL_LABELS

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless((ROOT / "data/current_run.json").exists(), "Importe as fontes reais antes deste teste de integração.")
class RealDashboardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.local_mode=patch.dict(os.environ,{"JACARE_PUBLIC_MODE":"false", "JACARE_AUTH_MODE":"local"})
        cls.local_mode.start()
        cls.addClassCleanup(cls.local_mode.stop)

    def app(self, page):
        app = AppTest.from_file(str(ROOT / "app/streamlit_app.py"), default_timeout=30).run()
        app.sidebar.radio[0].set_value(page).run()
        self.assertFalse(app.exception, [error.message for error in app.exception])
        return app

    def test_fifteen_narratives_match_real_answers(self):
        manifest = json.loads((ROOT / "data/current_run.json").read_text(encoding="utf-8"))
        answers = json.loads((ROOT / manifest["analysis_report"]).with_name("analysis_results.json").read_text(encoding="utf-8"))
        self.assertEqual([answer["id"] for answer in answers], list(range(1,16)))
        self.assertEqual(len(QUESTION_TITLES), 15)
        self.assertEqual(len(INTERPRETATIONS), 15)
        for answer in answers:
            with self.subTest(question=answer["id"]):
                text = answer_summary(answer)
                self.assertTrue(text)
                self.assertNotIn("None", text)

    def test_every_page_loads(self):
        app = self.app("Visão geral")
        for page in app.sidebar.radio[0].options:
            with self.subTest(page=page):
                app.sidebar.radio[0].set_value(page).run()
                self.assertFalse(app.exception, [error.message for error in app.exception])

    def test_every_question_can_be_selected(self):
        app = self.app("15 perguntas e respostas")
        self.assertEqual(len(app.subheader), 15)
        for number in range(1,16):
            with self.subTest(question=number):
                app.selectbox[0].set_value(number).run()
                self.assertFalse(app.exception)
                self.assertEqual(len(app.subheader), 1)
                self.assertIn(QUESTION_TITLES[number-1], app.subheader[0].value)

    def test_both_ml_targets_explain_error(self):
        app = self.app("Machine Learning")
        for target in ("paid_orders", "total_received_brl"):
            with self.subTest(target=target):
                app.selectbox(key="ml_target").set_value(target).run()
                self.assertFalse(app.exception)
                self.assertFalse(app.error, [error.value for error in app.error])
                self.assertTrue(any("Erro" in metric.label for metric in app.metric))
                self.assertTrue(app.warning)

    def test_ml_compares_four_models_and_changes_forecast_horizon(self):
        app = self.app("Machine Learning")
        manifest = json.loads((ROOT / "data/current_run.json").read_text(encoding="utf-8"))
        metrics = json.loads((ROOT / manifest["forecast_metrics"]).read_text(encoding="utf-8"))
        for target in ("paid_orders", "total_received_brl"):
            with self.subTest(target=target):
                app.selectbox(key="ml_target").set_value(target).run()
                self.assertFalse(app.exception)
                self.assertFalse(app.error)
                table_text="\n".join(frame.value.to_string() for frame in app.dataframe)
                for label in MODEL_LABELS.values():
                    self.assertIn(label,table_text)
                # O rádio deve aceitar 7 e 14 dias sem disparar uma nova ingestão.
                for days in (7,14):
                    app.radio(key="ml_horizon").set_value(days).run()
                    self.assertFalse(app.exception)
                    self.assertFalse(app.error)
                    future=next((frame.value for frame in app.dataframe if any("Estimativa" in str(column) for column in frame.value.columns)),None)
                    self.assertIsNotNone(future,"Falta a tabela de estimativas futuras.")
                    self.assertEqual(len(future),days)
                    forecast=metrics["targets"][target]["experimental_forecast"][:days]
                    self.assertEqual(len(forecast),len(future))
                    self.assertEqual(future["Estimativa do modelo"].tolist(),[row["prediction"] for row in forecast])
                    self.assertEqual([str(value)[:10] for value in future["Data"]],[row["date"] for row in forecast])
                    self.assertEqual(future["Situação"].tolist(),["Funcionamento previsto" if row["scheduled_open"] else "Fechamento planejado" for row in forecast])

    def test_ml_explains_calendar_and_historical_forecast_limit(self):
        app = self.app("Machine Learning")
        self.assertFalse(app.error)
        text="\n".join(item.value for items in (app.markdown,app.caption,app.info,app.warning) for item in items)
        self.assertTrue("18:30" in text or "18h30" in text)
        self.assertTrue("23:00" in text or "23h" in text)
        self.assertIn("segunda",text.lower())
        self.assertTrue("atual" in text.lower() and "histórico" in text.lower())
        self.assertTrue("holdout" in text.lower() or "teste final" in text.lower() or "testes finais" in text.lower())
        self.assertIn("não",text.lower())

    def test_ml_monthly_projection_matches_real_model_results(self):
        app=self.app("Machine Learning")
        manifest=json.loads((ROOT / "data/current_run.json").read_text(encoding="utf-8"))
        metrics=json.loads((ROOT / manifest["forecast_metrics"]).read_text(encoding="utf-8"))
        for target in ("paid_orders","total_received_brl"):
            with self.subTest(target=target):
                app.selectbox(key="ml_target").set_value(target).run()
                self.assertFalse(app.exception)
                self.assertFalse(app.error)
                projection=metrics["targets"][target]["monthly_projection"]
                rows=projection["predictions"]
                monthly=next((frame.value for frame in app.dataframe if "Projeção diária" in frame.value.columns),None)
                self.assertIsNotNone(monthly,"Falta a projeção mensal detalhada.")
                self.assertEqual(len(monthly),projection["summary"]["predicted_calendar_days"])
                self.assertEqual(monthly["Projeção diária"].tolist(),[row["prediction"] for row in rows])
                self.assertEqual([str(value)[:10] for value in monthly["Data"]],[row["date"] for row in rows])
                labels={metric.label for metric in app.metric}
                self.assertIn("Dias de funcionamento planejados",labels)
                self.assertIn("Horizonte desde a origem",labels)
                self.assertTrue(any(label.startswith("Total projetado —") for label in labels))
                text="\n".join(item.value for items in (app.markdown,app.caption,app.info,app.warning) for item in items).lower()
                self.assertIn(str(projection["horizon_from_origin_days"]),text)
                self.assertTrue("sete dias" in text or "7 dias" in text)
                self.assertIn("explorat",text)
                self.assertIn("origem",text)
                if projection["month"]=="2026-09":
                    self.assertEqual(len(monthly),30)
                    self.assertIn("Total projetado — setembro",labels)

    def test_monthly_evolution_explains_real_values_as_a_line(self):
        app=self.app("Visão geral")
        self.assertTrue(any(item.value=="Evolução mensal" for item in app.subheader))
        text="\n".join(item.value for items in (app.markdown,app.caption) for item in items).lower()
        self.assertIn("a linha mostra a evolução",text)
        self.assertIn("não lucro ou projeções",text)
        # Streamlit atual usa vega_lite_chart; mantenha compatibilidade com o tipo antigo.
        charts=list(app.get("vega_lite_chart"))+list(app.get("arrow_vega_lite_chart"))
        specs=[json.loads(chart.proto.spec) for chart in charts]
        def contains(node,key,value):
            if isinstance(node,dict):
                return node.get(key)==value or any(contains(child,key,value) for child in node.values())
            if isinstance(node,list):
                return any(contains(child,key,value) for child in node)
            return False
        monthly=[spec for spec in specs if contains(spec,"field","month") or contains(spec,"field","Mês")]
        self.assertTrue(monthly,"Falta o gráfico mensal renderizado.")
        self.assertTrue(all(contains(spec,"type","line") or contains(spec,"mark","line") for spec in monthly))

    def test_instagram_followers_has_definition_caution(self):
        app = self.app("Marketing")
        app.selectbox(key="social_metric").set_value("followers").run()
        self.assertFalse(app.exception)
        self.assertTrue(any("não o tratamos como o total da base" in item.value for item in app.markdown))


if __name__ == "__main__":
    unittest.main()
