"""Auditoria de integração contra a geração ativa e as fontes reais locais."""

import hashlib
import json
import math
import unittest
from datetime import date, timedelta
from pathlib import Path

import duckdb
import joblib
import pandas as pd
import yaml
from threadpoolctl import threadpool_limits

from jacare_analytics.business_calendar import freshness, is_open, load_calendar
from jacare_analytics.forecast_backtest import BASELINES, FEATURE_COLUMNS, MODEL_LABELS, _forecast, _read_series, _score
from jacare_analytics.pipeline import audit_warehouse
from jacare_analytics.source_files import collect_local, collect_uploads

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless((ROOT / "data/current_run.json").exists(), "Importe as fontes reais para auditar a geração.")
class RealPipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads((ROOT / "data/current_run.json").read_text(encoding="utf-8"))
        cls.run_dir = (ROOT / cls.manifest["warehouse"]).parent
        cls.source = json.loads((ROOT / cls.manifest["source_manifest"]).read_text(encoding="utf-8"))
        cls.metrics = json.loads((ROOT / cls.manifest["forecast_metrics"]).read_text(encoding="utf-8"))

    def test_local_and_zip_sources_match_active_hashes(self):
        local = collect_local(ROOT)
        archives = list(ROOT.glob("*.zip"))
        if archives:
            uploaded = collect_uploads((path.name,path.read_bytes()) for path in archives)
            self.assertEqual(set(local),set(uploaded))
            self.assertEqual({k:v.sha256 for k,v in local.items()}, {k:v.sha256 for k,v in uploaded.items()})
        self.assertEqual({k:v.sha256 for k,v in local.items()}, {k:v["sha256"] for k,v in self.manifest["sources"].items()})

    def test_live_warehouse_reconciles_with_independent_source_profile(self):
        result = audit_warehouse(ROOT / self.manifest["warehouse"],self.source)
        self.assertTrue(result["all_passed"])
        self.assertEqual(result,self.manifest["quality"])

    def test_all_sql_models_are_documented_built_and_tested(self):
        documented = {row["name"] for row in yaml.safe_load((ROOT / "warehouse/models/_models.yml").read_text(encoding="utf-8"))["models"]}
        sql_models = {path.stem for path in (ROOT / "warehouse/models").rglob("*.sql")}
        self.assertEqual(documented,sql_models)
        result = json.loads((self.run_dir / "dbt/run_results.json").read_text(encoding="utf-8"))["results"]
        built = {row["unique_id"].split(".")[-1] for row in result if row["unique_id"].startswith("model.") and row["status"]=="success"}
        tested = {row["unique_id"].split(".")[-1] for row in result if row["unique_id"].startswith("test.") and row["status"]=="pass"}
        self.assertEqual(sql_models,built)
        self.assertEqual({p.stem for p in (ROOT / "warehouse/tests").glob("*.sql")},tested)

    def test_all_fifteen_answers_equal_current_sql(self):
        answers = json.loads((self.run_dir / "analysis/analysis_results.json").read_text(encoding="utf-8"))
        self.assertEqual([item["id"] for item in answers],list(range(1,16)))
        with duckdb.connect(str(ROOT / self.manifest["warehouse"]),read_only=True) as connection:
            for item in answers:
                results=[]
                for sql in (ROOT / "sql/business" / item["sql"]).read_text(encoding="utf-8").split(";"):
                    if sql.strip():
                        frame=connection.execute(sql).df()
                        results.append(frame.astype(object).where(pd.notna(frame),None).to_dict(orient="records"))
                canonical=json.loads(json.dumps(results,default=str,allow_nan=False))
                # Sem ORDER BY, SQL não garante a ordem das linhas; compare todo o conteúdo.
                ordered=lambda groups:[sorted(group,key=lambda row:json.dumps(row,sort_keys=True)) for group in groups]
                self.assertEqual(ordered(canonical),ordered(item["results"]),item["sql"])

    def test_presentation_marts_do_not_expose_individual_keys(self):
        forbidden={"customer_key","order_key","customer_name","phone","address","email","notes","review_text"}
        with duckdb.connect(str(ROOT / self.manifest["warehouse"]),read_only=True) as connection:
            marts=connection.execute("select table_name from information_schema.tables where table_schema='analytics' and starts_with(table_name,'fct_')").fetchall()
            for (name,) in marts:
                columns={row[0] for row in connection.execute(f'describe analytics."{name}"').fetchall()}
                self.assertFalse(columns & forbidden,name)
        for file in (self.run_dir / "analysis").glob("*.json"):
            for key in ("customer_key", "order_key", "review_text", "customer_name"):
                self.assertNotIn(f'"{key}"',file.read_text(encoding="utf-8"))

    def test_ml_missing_targets_metrics_and_both_baseline_gates(self):
        path=self.run_dir / "processed/daily_sales_ml.csv"
        dates,targets=_read_series(path)
        self.assertEqual(self.metrics["schema_version"],4)
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),self.metrics["series_sha256"])
        self.assertEqual(self.metrics["series_sha256"],self.manifest["series_sha256"])
        self.assertEqual(sum(not math.isfinite(v) for v in targets["paid_orders"]),self.manifest["quality"]["missing_days"])
        self.assertEqual(self.metrics["missing_target_days"],self.manifest["quality"]["missing_days"])
        self.assertEqual(self.metrics["forecast_horizon_days"],14)
        self.assertEqual(self.metrics["splits"],8)
        self.assertEqual(self.metrics["test_size_days"],7)
        self.assertEqual(self.metrics["model_labels"],MODEL_LABELS)
        estimators=(*MODEL_LABELS,*BASELINES)
        for target,result in self.metrics["targets"].items():
            with self.subTest(target=target):
                self.assertEqual(set(result["candidate_models"]),set(estimators))
                self.assertEqual(result["selection_folds"],6)
                self.assertEqual(result["holdout_folds"],2)
                self.assertLess(result["selection_end"],result["holdout_start"])
            rows=result["backtest_predictions"]
            comparable=[row for row in rows if row["comparable"]]
            self.assertEqual(len(comparable),result["test_days"])
            for estimator in ("ml","seasonal_naive","moving_average_7d"):
                self.assertEqual(_score([r["actual"] for r in comparable],[r[estimator] for r in comparable]),result[estimator])
            # Seis abordagens são pontuadas sobre exatamente as mesmas datas reais.
            for estimator in estimators:
                for stage in ("overall","selection","holdout"):
                    observed=[row for row in comparable if stage=="overall" or row["stage"]==stage]
                    expected=_score([row["actual"] for row in observed],[row[estimator] for row in observed])
                    self.assertEqual(expected,result["candidate_models"][estimator][stage])
            # Refaça a escolha usando apenas as seis primeiras janelas, sem o holdout.
            selection=[row for row in comparable if row["stage"]=="selection"]
            selection_mae={name:_score([r["actual"] for r in selection],[r[name] for r in selection])["mae"] for name in MODEL_LABELS}
            selected=min(MODEL_LABELS,key=lambda name:(selection_mae[name],name))
            self.assertEqual(selected,result["selected_model"])
            self.assertTrue(all(row["date"]<=result["selection_end"] for row in selection))
            holdout=[row for row in comparable if row["stage"]=="holdout"]
            self.assertEqual(len(holdout),result["holdout_comparable_days"])
            self.assertTrue(all(row["date"]>=result["holdout_start"] for row in holdout))
            self.assertEqual([row["stage"] for row in result["fold_details"]],["selection"]*6+["holdout"]*2)
            for fold in result["fold_details"]:
                self.assertLess(fold["train_end"],fold["test_start"])
                fold_rows=[row for row in comparable if row["fold"]==fold["fold"]]
                self.assertEqual(fold["compared_days"],len(fold_rows))
                train_end=date.fromisoformat(fold["train_end"])
                observed_train=sum(math.isfinite(value) for day,value in zip(dates[28:],targets[target][28:]) if day<=train_end)
                self.assertEqual(fold["train_observed_days"],observed_train)
                for estimator in estimators:
                    self.assertEqual(_score([row["actual"] for row in fold_rows],[row[estimator] for row in fold_rows]),fold[estimator])
                self.assertEqual(fold["ml"],fold[selected])
            expected_wins={baseline:sum(fold["ml"]["mae"]<fold[baseline]["mae"] for fold in result["fold_details"]) for baseline in BASELINES}
            self.assertEqual(expected_wins,result["fold_wins"])
            expected_gains={baseline:1-result["ml"]["mae"]/result[baseline]["mae"] if result[baseline]["mae"] else None for baseline in BASELINES}
            self.assertEqual(expected_gains,result["mae_improvement_by_baseline"])
            gates={baseline:(gain is not None and gain>=0.10 and result["fold_wins"][baseline]/result["folds"]>=0.75) for baseline,gain in result["mae_improvement_by_baseline"].items()}
            self.assertEqual(gates,result["baseline_gates_passed"])
            holdout_gates={baseline:result["candidate_models"][selected]["holdout"]["mae"]<result["candidate_models"][baseline]["holdout"]["mae"] for baseline in BASELINES}
            self.assertEqual(holdout_gates,result["holdout_gates_passed"])
            self.assertEqual(all(gates.values()) and result["test_days"]>=28 and len(holdout)>=10 and all(holdout_gates.values()),result["statistical_gate_passed"])
            self.assertFalse(result["operational_approved"])
            actual=dict(zip((d.isoformat() for d in dates),targets[target]))
            for row in rows:
                expected_comparable=row["actual"] is not None and all(row[name] is not None and math.isfinite(row[name]) for name in estimators)
                self.assertEqual(row["comparable"],expected_comparable)
                self.assertEqual(row["ml"],row[selected])
                if math.isfinite(actual[row["date"]]):
                    self.assertEqual(actual[row["date"]],row["actual"])
                else:
                    self.assertIsNone(row["actual"])
                    self.assertFalse(row["comparable"])

    def test_saved_models_reproduce_fourteen_day_forecast_with_calendar(self):
        artifact=joblib.load(self.run_dir / "ml/forecast_models.joblib")
        self.assertEqual(artifact["series_sha256"],self.metrics["series_sha256"])
        self.assertEqual(artifact["calendar"],self.metrics["calendar"])
        self.assertEqual(tuple(artifact["feature_columns"]),FEATURE_COLUMNS)
        self.assertEqual(set(artifact["models"]),set(self.metrics["targets"]))
        self.assertEqual(set(artifact["candidate_models"]),set(self.metrics["targets"]))
        dates,targets=_read_series(self.run_dir / "processed/daily_sales_ml.csv")
        with threadpool_limits(limits=1):
            for target,model in artifact["models"].items():
                result=self.metrics["targets"][target]
                rows=result["experimental_forecast"]
                self.assertEqual(len(rows),14)
                first=date.fromisoformat(rows[0]["date"])
                self.assertEqual(first,dates[-1]+timedelta(days=1))
                predictions=_forecast(model,targets[target],first,14,artifact["calendar"])
                self.assertEqual(predictions,[row["prediction"] for row in rows])
                candidates=artifact["candidate_models"][target]
                self.assertEqual(set(candidates),set(MODEL_LABELS))
                selected_predictions=_forecast(candidates[result["selected_model"]],targets[target],first,14,artifact["calendar"])
                self.assertEqual(predictions,selected_predictions)
                for offset,row in enumerate(rows):
                    day=first+timedelta(days=offset)
                    self.assertEqual(row["date"],day.isoformat())
                    opened=is_open(day,artifact["calendar"])
                    self.assertEqual(row["scheduled_open"],opened)
                    self.assertEqual(row["prediction_origin"],"model" if opened else "calendar_closed")
                    self.assertGreaterEqual(row["residual_band_low"],0)
                    self.assertLessEqual(row["residual_band_low"],row["residual_band_high"])
                    if not opened:
                        self.assertEqual(row["prediction"],0.0)
                        self.assertEqual(row["residual_band_low"],0.0)
                        self.assertEqual(row["residual_band_high"],0.0)
                # O fechamento é regra de estimativa futura, nunca alvo real inventado.
                for candidate in candidates.values():
                    future=_forecast(candidate,targets[target],first,14,artifact["calendar"])
                    self.assertTrue(all(value==0 for offset,value in enumerate(future) if not is_open(first+timedelta(days=offset),artifact["calendar"])))

    def test_business_calendar_preserves_real_history_and_matches_current_hours(self):
        calendar=load_calendar(ROOT)
        self.assertEqual(calendar,self.metrics["calendar"])
        self.assertEqual(calendar["timezone"],"America/Sao_Paulo")
        self.assertEqual(calendar["open_weekdays"],[1,2,3,4,5,6])
        self.assertEqual(calendar["opens_at"],"18:30")
        self.assertEqual(calendar["closes_at"],"23:00")
        self.assertFalse(calendar["historical_exceptions_validated"])
        dates,targets=_read_series(self.run_dir / "processed/daily_sales_ml.csv")
        as_of=date.fromisoformat(self.metrics["freshness"]["as_of_date"])
        self.assertEqual(self.metrics["freshness"],freshness(dates[-1],calendar,as_of))
        missing=sum(not math.isfinite(value) for value in targets["paid_orders"])
        self.assertEqual(missing,self.manifest["quality"]["missing_days"])
        # Preserve as 36 lacunas deste lote real, inclusive segundas sem registro.
        if self.metrics["source_start"]=="2026-01-02" and self.metrics["source_end"]=="2026-08-19":
            self.assertEqual(missing,36)
        with duckdb.connect(str(ROOT / self.manifest["warehouse"]),read_only=True) as connection:
            actual=connection.execute("select cast(opened_at as date) as day,count(*) as orders from analytics.stg_orders where order_status='paid' group by 1").fetchall()
            actual_counts={day:count for day,count in actual}
            for day,value in zip(dates,targets["paid_orders"]):
                if day in actual_counts:
                    self.assertEqual(value,actual_counts[day])
                else:
                    self.assertFalse(math.isfinite(value),day.isoformat())
            monday_count,outside_hours=connection.execute("select count(*) filter(where dayofweek(opened_at)=1),count(*) filter(where cast(opened_at as time)<cast(? as time) or cast(opened_at as time)>=cast(? as time)) from analytics.stg_orders where order_status='paid'",[calendar["opens_at"],calendar["closes_at"]]).fetchone()
        self.assertEqual(self.metrics["calendar_review"]["paid_orders_on_monday"],monday_count)
        self.assertEqual(self.metrics["calendar_review"]["paid_orders_outside_reference_hours"],outside_hours)

    def test_monthly_projection_reproduces_bridge_and_complete_month(self):
        artifact=joblib.load(self.run_dir / "ml/forecast_models.joblib")
        dates,targets=_read_series(self.run_dir / "processed/daily_sales_ml.csv")
        origin=dates[-1]
        start=date(origin.year+(origin.month==12),origin.month%12+1,1)
        following=date(start.year+(start.month==12),start.month%12+1,1)
        end=following-timedelta(days=1)
        first_forecast=origin+timedelta(days=1)
        bridge=(start-first_forecast).days
        horizon=(end-origin).days
        with threadpool_limits(limits=1):
            for target,model in artifact["models"].items():
                with self.subTest(target=target):
                    result=self.metrics["targets"][target]
                    projection=result["monthly_projection"]
                    self.assertEqual(projection["month"],start.strftime("%Y-%m"))
                    self.assertEqual(projection["forecast_origin"],origin.isoformat())
                    self.assertEqual(projection["start"],start.isoformat())
                    self.assertEqual(projection["end"],end.isoformat())
                    self.assertEqual(projection["bridge_days"],bridge)
                    self.assertEqual(projection["horizon_from_origin_days"],horizon)
                    rows=projection["predictions"]
                    self.assertEqual(len(rows),(end-start).days+1)
                    # Reproduza a ponte inteira antes de isolar os dias do mês.
                    complete=_forecast(model,targets[target],first_forecast,horizon,artifact["calendar"])
                    self.assertEqual([row["prediction"] for row in rows],complete[bridge:])
                    self.assertEqual(complete[:14],[row["prediction"] for row in result["experimental_forecast"]])
                    for offset,row in enumerate(rows):
                        day=start+timedelta(days=offset)
                        self.assertEqual(row["date"],day.isoformat())
                        opened=is_open(day,artifact["calendar"])
                        self.assertEqual(row["scheduled_open"],opened)
                        self.assertEqual(row["prediction_origin"],"model" if opened else "calendar_closed")
                        self.assertGreaterEqual(row["prediction"],0)
                        if not opened:
                            self.assertEqual(row["prediction"],0.0)
                    self.assertEqual(projection["summary"],{
                        "predicted_total":sum(row["prediction"] for row in rows),
                        "predicted_open_days":sum(row["scheduled_open"] for row in rows),
                        "predicted_calendar_days":len(rows),
                    })
                    policy=projection["validation_policy"].lower()
                    self.assertIn("sete dias",policy)
                    self.assertIn("exploratória",policy)
                    self.assertIn("não",policy)
                    self.assertFalse(result["operational_approved"])
                    # Expectativas deste lote real fornecido, nunca observações criadas.
                    if origin==date(2026,8,19):
                        self.assertEqual(projection["month"],"2026-09")
                        self.assertEqual(len(rows),30)
                        self.assertEqual(bridge,12)
                        self.assertEqual(horizon,42)
                        self.assertEqual(projection["summary"]["predicted_open_days"],26)

    def test_incomplete_clicks_never_produce_cpc_or_ctr(self):
        with duckdb.connect(str(ROOT / self.manifest["warehouse"]),read_only=True) as connection:
            unknown=connection.execute("select count(*) from analytics.fct_marketing_daily where link_clicks_missing_rows>0 and (cpc_brl is not null or link_ctr is not null)").fetchone()[0]
            self.assertEqual(unknown,0)
            missing=connection.execute("select coalesce(sum(link_clicks_missing_rows),0) from analytics.stg_meta_ads_daily").fetchone()[0]
            self.assertEqual(missing,self.source["marketing"].get("missing_link_click_rows",0))


if __name__ == "__main__":
    unittest.main()
