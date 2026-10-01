"""Contratos temporais verificados somente na geração dos dados reais."""

from __future__ import annotations

import json
import math
import unittest
from datetime import date, timedelta
from pathlib import Path

import joblib
import numpy as np
from threadpoolctl import threadpool_limits

from jacare_analytics.business_calendar import is_open
from jacare_analytics.forecast_backtest import (
    BASELINES,
    MODEL_LABELS,
    _forecast,
    _read_series,
    _score,
    render_backtest_report,
)


class ForecastLogicRealDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[1]
        active = cls.root / "data/current_run.json"
        if not active.exists():
            raise unittest.SkipTest("Importe os dados reais para gerar os artefatos do experimento.")
        cls.manifest = json.loads(active.read_text(encoding="utf-8"))
        cls.run_dir = (cls.root / cls.manifest["warehouse"]).parent
        cls.metrics = json.loads((cls.root / cls.manifest["forecast_metrics"]).read_text(encoding="utf-8"))
        if cls.metrics["schema_version"] != 4:
            raise unittest.SkipTest("Reprocesse os dados reais para atualizar o experimento para a versão 4.")
        cls.dates, cls.targets = _read_series(cls.run_dir / "processed/daily_sales_ml.csv")

    def test_algorithm_choice_uses_selection_only(self):
        for result in self.metrics["targets"].values():
            self.assertEqual(result["selection_folds"], 6)
            self.assertEqual(result["holdout_folds"], 2)
            self.assertLess(result["selection_end"], result["holdout_start"])
            selected = min(MODEL_LABELS, key=lambda name: (result["candidate_models"][name]["selection"]["mae"], name))
            self.assertEqual(result["selected_model"], selected)
            for row in result["backtest_predictions"]:
                self.assertEqual(row["ml"], row[selected])
                self.assertEqual(row["stage"], "selection" if row["fold"] <= 6 else "holdout")
            self.assertFalse(result["operational_approved"])

    def test_all_six_approaches_have_independently_reproducible_scores(self):
        for result in self.metrics["targets"].values():
            rows = result["backtest_predictions"]
            for name in (*MODEL_LABELS, *BASELINES):
                for stage in ("selection", "holdout", "overall"):
                    comparable = [row for row in rows if row["comparable"] and (stage == "overall" or row["stage"] == stage)]
                    score = _score([row["actual"] for row in comparable], [row[name] for row in comparable])
                    self.assertAlmostEqual(result["candidate_models"][name][stage]["mae"], score["mae"])
                    self.assertAlmostEqual(result["candidate_models"][name][stage]["wape"], score["wape"])
            for row in rows:
                expected = row["actual"] is not None and all(row[name] is not None for name in (*MODEL_LABELS, *BASELINES))
                self.assertEqual(row["comparable"], expected)

    def test_exploratory_band_uses_only_final_errors(self):
        for result in self.metrics["targets"].values():
            final = [row for row in result["backtest_predictions"] if row["comparable"] and row["stage"] == "holdout"]
            self.assertEqual(result["residual_band_sample_size"], len(final))
            low, high = np.quantile([row["actual"] - row["ml"] for row in final], [0.10, 0.90])
            for row in result["experimental_forecast"]:
                if row["scheduled_open"]:
                    self.assertAlmostEqual(row["residual_band_low"], max(0, row["prediction"] + low))
                    self.assertAlmostEqual(row["residual_band_high"], max(0, row["prediction"] + high))

    def test_saved_model_forecasts_follow_calendar_without_mutating_history(self):
        artifact = joblib.load(self.run_dir / "ml/forecast_models.joblib")
        self.assertEqual(artifact["calendar"], self.metrics["calendar"])
        self.assertEqual(artifact["series_sha256"], self.metrics["series_sha256"])
        with threadpool_limits(limits=1):
            for target, history in self.targets.items():
                before = history.copy()
                predicted = _forecast(artifact["models"][target], history, self.dates[-1] + timedelta(days=1), 14, artifact["calendar"])
                rows = self.metrics["targets"][target]["experimental_forecast"]
                self.assertEqual(len(rows), 14)
                self.assertTrue(all(a == b or (math.isnan(a) and math.isnan(b)) for a, b in zip(before, history)))
                self.assertEqual(set(artifact["candidate_models"][target]), set(MODEL_LABELS))
                for estimate, row in zip(predicted, rows):
                    self.assertAlmostEqual(estimate, row["prediction"])
                    day = date.fromisoformat(row["date"])
                    self.assertEqual(row["scheduled_open"], is_open(day, artifact["calendar"]))
                    if not row["scheduled_open"]:
                        self.assertEqual(row["prediction_origin"], "calendar_closed")
                        self.assertEqual(row["prediction"], 0)
                        self.assertEqual(row["residual_band_low"], 0)
                        self.assertEqual(row["residual_band_high"], 0)

    def test_report_explains_models_real_dates_and_unvalidated_longer_horizon(self):
        report = render_backtest_report(self.metrics)
        for label in MODEL_LABELS.values():
            self.assertIn(label, report)
        self.assertIn("MAE teste final", report)
        self.assertIn("totais incluem seleção", report)
        self.assertIn("oito a quatorze dias", report)
        self.assertIn("não garante cobertura", report)
        start = self.dates[-1] + timedelta(days=1)
        self.assertIn(start.strftime("%d/%m/%Y"), report)
        self.assertIn((start + timedelta(days=13)).strftime("%d/%m/%Y"), report)
        self.assertIn("18:30", report)
        if not self.metrics["freshness"]["supports_current_week"]:
            self.assertIn("não é uma previsão atual", report)

    def test_monthly_projection_preserves_bridge_and_reproduces_saved_model(self):
        artifact = joblib.load(self.run_dir / "ml/forecast_models.joblib")
        origin = self.dates[-1]
        with threadpool_limits(limits=1):
            for target, history in self.targets.items():
                result = self.metrics["targets"][target]
                projection = result["monthly_projection"]
                before = history.copy()
                start = date.fromisoformat(projection["start"])
                end = date.fromisoformat(projection["end"])
                self.assertEqual(projection["forecast_origin"], origin.isoformat())
                self.assertEqual(start.day, 1)
                self.assertEqual(projection["bridge_days"], (start - origin - timedelta(days=1)).days)
                self.assertEqual(projection["horizon_from_origin_days"], (end - origin).days)
                recursive = _forecast(artifact["models"][target], history, origin + timedelta(days=1), projection["horizon_from_origin_days"], artifact["calendar"])
                expected = recursive[projection["bridge_days"]:]
                rows = projection["predictions"]
                self.assertEqual(len(rows), (end - start).days + 1)
                self.assertEqual(rows[0]["date"], start.isoformat())
                self.assertEqual(rows[-1]["date"], end.isoformat())
                self.assertTrue(all(a == b or (math.isnan(a) and math.isnan(b)) for a, b in zip(before, history)))
                for offset, (estimate, row) in enumerate(zip(expected, rows)):
                    self.assertAlmostEqual(estimate, row["prediction"])
                    self.assertEqual(date.fromisoformat(row["date"]), start + timedelta(days=offset))
                    self.assertEqual(row["scheduled_open"], is_open(start + timedelta(days=offset), artifact["calendar"]))
                    self.assertNotIn("residual_band_low", row)
                    self.assertNotIn("residual_band_high", row)
                    if not row["scheduled_open"]:
                        self.assertEqual(row["prediction"], 0)
                        self.assertEqual(row["prediction_origin"], "calendar_closed")
                summary = projection["summary"]
                self.assertAlmostEqual(summary["predicted_total"], sum(row["prediction"] for row in rows))
                self.assertEqual(summary["predicted_open_days"], sum(row["scheduled_open"] for row in rows))
                self.assertEqual(summary["predicted_calendar_days"], len(rows))
                # Valores específicos são conferidos somente quando esta é a origem real da geração.
                if origin.isoformat() == "2026-08-19":
                    self.assertEqual(projection["month"], "2026-09")
                    self.assertEqual(projection["bridge_days"], 12)
                    self.assertEqual(projection["horizon_from_origin_days"], 42)
                    self.assertEqual(summary["predicted_calendar_days"], 30)
                    self.assertEqual(summary["predicted_open_days"], 26)
                for short, long in zip(result["experimental_forecast"], recursive):
                    self.assertAlmostEqual(short["prediction"], long)
                self.assertIn("sete dias", projection["validation_policy"])
                self.assertIn("Não há intervalo mensal calibrado", projection["validation_policy"])


if __name__ == "__main__":
    unittest.main()
