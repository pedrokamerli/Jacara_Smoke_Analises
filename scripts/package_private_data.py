"""Snapshot privado portátil: materializa dbt, sem originais nem segredo HMAC."""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import tarfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

import duckdb

from jacare_analytics.pipeline import audit_warehouse
from jacare_analytics.runtime_config import load_runtime_config
from jacare_analytics.source_files import collect_local

ROOT = Path(__file__).resolve().parents[1]
TABLES = frozenset({
    "stg_orders", "stg_items", "stg_appdelivery_daily", "stg_food99_daily",
    "stg_ifood_daily", "stg_ifood_products", "stg_instagram_daily", "stg_meta_ads_daily",
    "fct_appdelivery_reconciliation", "fct_channel_sales", "fct_customer_activity_monthly",
    "fct_customer_recurrence", "fct_daily_sales", "fct_food99_summary",
    "fct_ifood_reconciliation", "fct_instagram_daily", "fct_marketing_daily",
    "fct_product_performance", "fct_sales_by_hour", "fct_weekly_sales",
})


def portable_warehouse(source: Path, destination: Path) -> None:
    """CTAS remove views com caminhos absolutos e mantém resultados SQL/dbt."""
    if destination.exists():
        raise ValueError("Não sobrescrever snapshot existente")
    with duckdb.connect(str(destination)) as connection:
        escaped = str(source.resolve()).replace("'", "''")
        connection.execute(f"ATTACH '{escaped}' AS original (READ_ONLY)")
        names = {row[0] for row in connection.execute(
            "select table_name from information_schema.tables where table_catalog='original' and table_schema='analytics'"
        ).fetchall()}
        if names != TABLES:
            raise ValueError("Modelos do banco fora da allowlist")
        connection.execute("CREATE SCHEMA analytics")
        for name in sorted(TABLES):
            connection.execute(f'CREATE TABLE analytics."{name}" AS SELECT * FROM original.analytics."{name}"')
            before = connection.execute(f'SELECT count(*) FROM original.analytics."{name}"').fetchone()
            after = connection.execute(f'SELECT count(*) FROM analytics."{name}"').fetchone()
            if before != after:
                raise ValueError("Snapshot não preservou contagem de registros")
        connection.execute("DETACH original")
        connection.execute("CHECKPOINT")


def main() -> None:
    config = load_runtime_config(ROOT, {"JACARE_PUBLIC_MODE": "false"})
    manifest = json.loads(config.current_manifest_path.read_text(encoding="utf-8"))
    if manifest.get("dataset_kind") not in (None, "real_confidential") or manifest.get("quality", {}).get("all_passed") is not True:
        raise ValueError("Somente geração real auditada pode ser instalada privadamente")
    source = json.loads(config.resolve_artifact(manifest["source_manifest"]).read_text(encoding="utf-8"))
    bundle = collect_local(ROOT)
    if not source.get("customer_pseudonymization_enabled") or not source.get("sources"):
        raise ValueError("Origem real e pseudonimização não comprovadas")
    for key, provenance in source["sources"].items():
        if key not in bundle or bundle[key].sha256 != provenance["sha256"]:
            raise ValueError("Fonte atual diverge da geração auditada")
    run_id = manifest["run_id"]
    if not re.fullmatch(r"[A-Za-z0-9_]+", run_id):
        raise ValueError("Identificador de geração inválido")
    tag = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "_" + uuid.uuid4().hex[:8]
    stage = ROOT / "data/private/deploy" / ("private-" + tag)
    run = stage / "data/runs" / run_id
    run.mkdir(parents=True, exist_ok=False)
    portable = run / "jacare_analytics.duckdb"
    portable_warehouse(config.resolve_artifact(manifest["warehouse"]), portable)
    if audit_warehouse(portable, source) != manifest["quality"]:
        raise ValueError("Auditoria portátil diverge da geração aprovada")
    members = [portable]
    for key in ("analysis_report", "forecast_metrics", "quality_report"):
        original = config.resolve_artifact(manifest[key])
        target = stage / manifest[key]
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(original, target)
        members.append(target)
    original_answers = config.resolve_artifact(manifest["analysis_report"]).with_name("analysis_results.json")
    answers = stage / manifest["analysis_report"]
    answers = answers.with_name("analysis_results.json")
    if original_answers.is_symlink() or not original_answers.is_file():
        raise ValueError("Respostas analíticas ausentes")
    shutil.copyfile(original_answers, answers)
    members.append(answers)
    # O dashboard só exige este arquivo para rastreabilidade; não enviar nomes/caminhos de origem.
    source_target = stage / manifest["source_manifest"]
    source_target.parent.mkdir(parents=True, exist_ok=True)
    source_target.write_text(json.dumps({
        "run_id": run_id, "source_start": manifest["source_start"],
        "source_end": manifest["source_end"], "dataset_kind": "real_confidential",
        "originals_transferred": False, "source_manifest_sha256": hashlib.sha256(
            config.resolve_artifact(manifest["source_manifest"]).read_bytes()).hexdigest(),
    }, indent=2), encoding="utf-8")
    members.append(source_target)
    manifest = {**manifest, "dataset_kind": "real_confidential", "sources": {}, "deployment_storage": "materialized_dbt_snapshot"}
    current = stage / "data/current_run.json"
    current.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    members.append(current)
    integrity = stage / "integrity.json"
    integrity.write_text(json.dumps({
        p.relative_to(stage).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in members
    }, indent=2), encoding="utf-8")
    members.append(integrity)
    archive_path = stage.with_suffix(".tar.gz")
    with tarfile.open(archive_path, "x:gz") as archive:
        for path in members:
            if path.is_symlink():
                raise ValueError("Links não permitidos")
            archive.add(path, arcname=path.relative_to(stage).as_posix(), recursive=False)
    print("Snapshot privado validado: banco portátil, narrativa, ML, auditoria e manifesto.")
    print("Sem originais, Parquet, modelos joblib, credenciais ou chave HMAC.")
    print(archive_path)
    print("SHA256:", hashlib.sha256(archive_path.read_bytes()).hexdigest())


if __name__ == "__main__":
    main()
