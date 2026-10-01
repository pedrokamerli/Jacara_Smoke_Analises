"""Atualização local isolada: publica uma geração apenas após dbt, auditoria e ML."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable

import duckdb

from .forecast_backtest import save_experiment, render_backtest_report
from .business_report import write_business_report
from .prepare_extracted import CUTOFF, prepare_bundle
from .source_files import SourceFile, collect_local
from .business_calendar import load_calendar

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def audit_warehouse(path: Path, source: dict[str, Any]) -> dict[str, Any]:
    with duckdb.connect(str(path), read_only=True) as connection:
        total = connection.execute("select sum(paid_orders), sum(amount_received_brl) from analytics.fct_daily_sales").fetchone()
        observed = connection.execute("select count(*) filter(where has_source_records), count(*) filter(where not has_source_records) from analytics.fct_daily_sales").fetchone()
        channels = connection.execute("select source_channel, count(*) from analytics.stg_orders where order_status='paid' group by 1 order by 2 desc").fetchall()
        linkage = connection.execute("select count(*) from analytics.stg_items i left join analytics.stg_orders o using(order_key) where o.order_key is null").fetchone()[0]
        allowed_orders = {"order_key", "opened_at", "closed_at", "order_status", "order_type", "source_channel", "delivery_type", "items_amount_brl", "service_fee_brl", "delivery_fee_brl", "order_total_brl", "amount_received_brl", "customer_key"}
        columns = {row[0] for row in connection.execute("describe analytics.stg_orders").fetchall()}
        allowed_items = {"order_key", "sold_at", "quantity", "unit_price_brl", "line_total_brl", "item_type", "product_name", "product_type", "product_category", "order_type", "order_status"}
        item_columns = {row[0] for row in connection.execute("describe analytics.stg_items").fetchall()}
        tests = {
            "paid_order_count_matches_preparation": int(total[0]) == source["expected_paid_orders"],
            "received_matches_preparation": abs(float(total[1]) - source["expected_received_brl"]) < 0.01,
            "paid_order_count_matches_raw": int(total[0]) == source["raw_paid_rows"],
            "received_matches_raw": abs(float(total[1]) - source["raw_received_brl"]) < 0.01,
            "items_have_orders": linkage == 0,
            "orders_follow_privacy_allowlist": columns == allowed_orders,
            "items_follow_privacy_allowlist": item_columns == allowed_items,
            "missing_calendar_days_match_source": int(observed[1]) == source["calendar_days_without_records"],
        }
        if source["marketing"]["available"]:
            tests["meta_ads_spend_matches_report_total"] = source["marketing"]["spend_reconciled"]
    report = {"checks": tests, "all_passed": all(tests.values()), "paid_orders": int(total[0]), "received_brl": round(float(total[1]), 2), "observed_days": int(observed[0]), "missing_days": int(observed[1]), "paid_orders_by_channel": dict(channels)}
    if not report["all_passed"]:
        failed = [key for key, value in tests.items() if not value]
        raise RuntimeError("Falha na reconciliação: " + ", ".join(failed))
    return report


def run_pipeline(
    bundle: dict[str, SourceFile], project_root: Path = PROJECT_ROOT,
    cutoff: date = CUTOFF, progress: Callable[[str], None] | None = None,
    *, demo: bool = False,
) -> dict[str, Any]:
    project_root = project_root.resolve()
    if demo and project_root == PROJECT_ROOT:
        raise ValueError("Demo exige workspace isolado; não pode substituir a geração real.")
    say = progress or (lambda message: None)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "_" + uuid.uuid4().hex[:8]
    run_dir = project_root / "data" / "runs" / run_id
    run_dir.mkdir(parents=True)
    processed = run_dir / "processed"
    say("Gerando dados sintéticos independentes" if demo else "Preparando arquivos reais e removendo identificadores diretos")
    if demo:
        from .demo import prepare_demo
        source = prepare_demo(processed)
        cutoff = date.fromisoformat(source["source_end"])
    else:
        source = prepare_bundle(bundle, processed, project_root / "data" / "private", cutoff)
    say("Construindo e verificando os modelos SQL/dbt")
    dbt_program = Path(sys.executable).with_name("dbt.exe" if os.name == "nt" else "dbt")
    executable = str(dbt_program) if dbt_program.exists() else shutil.which("dbt")
    if not executable:
        raise RuntimeError("dbt não encontrado no ambiente. Instale requirements.txt no ambiente do projeto.")
    profiles = project_root / "warehouse" / "profiles.yml"
    if not profiles.exists():
        shutil.copyfile(project_root / "warehouse" / "profiles.example.yml", profiles)
    warehouse_path = run_dir / "jacare_analytics.duckdb"
    env = os.environ.copy()
    env.update({"DBT_SEND_ANONYMOUS_USAGE_STATS": "false", "JACARE_DATA_DIR": processed.as_posix(), "JACARE_DUCKDB_PATH": warehouse_path.as_posix()})
    result = subprocess.run([executable, "build", "--project-dir", "warehouse", "--profiles-dir", "warehouse", "--target-path", str(run_dir / "dbt"), "--log-path", str(run_dir / "logs")], cwd=project_root, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300, check=False)
    if result.returncode:
        (run_dir / "dbt_failure.log").write_text(result.stdout + result.stderr, encoding="utf-8")
        raise RuntimeError(f"dbt build falhou; a geração anterior continua ativa. Consulte data/runs/{run_id}/dbt_failure.log.")
    dbt_result = json.loads((run_dir / "dbt/run_results.json").read_text(encoding="utf-8"))
    say("Reconciliando os totais com as planilhas de origem")
    quality = audit_warehouse(warehouse_path, source)
    say("Respondendo às 15 perguntas com consultas SQL agregadas")
    write_business_report(warehouse_path, project_root / "sql/business", run_dir / "analysis")
    (run_dir / "quality_report.json").write_text(json.dumps(quality, ensure_ascii=False, indent=2), encoding="utf-8")
    say("Avaliando Machine Learning com janelas temporais e baselines")
    calendar = load_calendar(project_root)
    with duckdb.connect(str(warehouse_path),read_only=True) as connection:
        closed_days, outside_hours = connection.execute("select count(*) filter(where dayofweek(opened_at)=1), count(*) filter(where cast(opened_at as time)<cast(? as time) or cast(opened_at as time)>=cast(? as time)) from analytics.stg_orders where order_status='paid'",[calendar["opens_at"],calendar["closes_at"]]).fetchone()
    metrics = save_experiment(processed / "daily_sales_ml.csv", run_dir / "ml",calendar)
    metrics["calendar_review"] = {"paid_orders_on_monday":closed_days, "paid_orders_outside_reference_hours":outside_hours, "policy":"Registros originais são preservados. Abertura do pedido pode anteceder atendimento; exceções históricas precisam ser confirmadas."}
    (run_dir / "ml/forecast_metrics.json").write_text(json.dumps(metrics,ensure_ascii=False,indent=2),encoding="utf-8")
    (run_dir / "ml/forecast_backtest.md").write_text(render_backtest_report(metrics), encoding="utf-8")
    manifest = {"schema_version": 1, "run_id": run_id, "updated_at_utc": datetime.now(timezone.utc).isoformat(), "cutoff": cutoff.isoformat(), "source_start": source["source_start"], "source_end": source["source_end"], "warehouse": warehouse_path.relative_to(project_root).as_posix(), "forecast_metrics": (run_dir / "ml" / "forecast_metrics.json").relative_to(project_root).as_posix(), "source_manifest": (processed / "source_manifest.json").relative_to(project_root).as_posix(), "quality_report": (run_dir / "quality_report.json").relative_to(project_root).as_posix(), "quality": quality, "sources": source["sources"], "ml_missing_days": metrics["missing_target_days"]}
    manifest.update({
        "dataset_kind": "synthetic" if demo else "real_confidential",
        "analysis_report": (run_dir / "analysis/analysis_report.md").relative_to(project_root).as_posix(),
        "series_sha256": metrics["series_sha256"],
        "dbt_models_built": sum(row["unique_id"].startswith("model.") for row in dbt_result["results"]),
        "dbt_tests_passed": sum(row["unique_id"].startswith("test.") and row["status"] == "pass" for row in dbt_result["results"]),
    })
    candidate = project_root / "data" / f"current_run.{run_id}.tmp"
    candidate.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(candidate, project_root / "data" / "current_run.json")
    say("Nova geração validada e publicada no dashboard local")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Atualiza preparação, SQL/dbt, qualidade e ML com fontes reais.")
    parser.add_argument("--source-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--cutoff", type=date.fromisoformat, default=CUTOFF)
    args = parser.parse_args()
    manifest = run_pipeline(collect_local(args.source_root), cutoff=args.cutoff, progress=lambda message: print(message, flush=True))
    print(f"Geração {manifest['run_id']}: {manifest['quality']['paid_orders']} pedidos pagos; verificações concluídas.")


if __name__ == "__main__":
    main()
