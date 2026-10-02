"""Exporta somente gerações sintéticas; dados reais nunca são públicos."""

from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import json
import math
import re
from datetime import date, datetime, timedelta, timezone
from calendar import monthrange
from pathlib import Path

from .dashboard_story import INTERPRETATIONS, answer_summary
from .runtime_config import PUBLIC_ARTIFACTS, load_runtime_config, validate_public_manifest
from .forecast_backtest import FEATURE_COLUMNS

ROOT = Path(__file__).resolve().parents[2]
MIN_GROUP = 5
RESULT_COLUMNS = frozenset("""
amount_received_brl average_acceptance_seconds average_finalization_seconds average_prep_minutes
average_received_per_customer average_ticket_brl commission_expense_brl comparable_days covered_days
cpc_brl customers delivery_fee_brl delivery_type descriptive_correlation dimension first_date
first_order_date first_seen_customers first_value frequency_group highest_value_rank highest_volume_rank
identified_customers identified_paid_orders impressions item_sales_brl item_type items_difference_brl
items_value_brl last_date last_order_date last_value late_preparation_orders link_clicks
link_clicks_missing_rows link_ctr lowest_value_rank lowest_volume_rank matching_dates metric_key
missing_days month_start observations observed_days order_status orders orders_containing_item
orders_with_both_timestamps paid_orders paired_dates payment_channel_fee_brl pdv_paid_orders
product_category product_name received_brl recency_group recurrence_rate recurring_customers
reported_dates reported_orders returning_customers sale_date sales_revenue_brl same_count_days
shop_revenue_brl source_channel spend_brl units_sold value week_start
""".split())
GROUP_COUNTS = frozenset({"customers", "identified_customers", "paid_orders", "orders", "orders_containing_item"})
CUSTOMER_PARTITIONS = frozenset({"first_seen_customers", "returning_customers", "recurring_customers"})
PRIVATE_FIELDS = frozenset({
    "customer_key", "order_key", "customer_id", "order_id", "email", "phone", "telefone",
    "address", "endereco", "nome", "cpf", "cnpj", "hmac_key", "sources", "source_manifest",
    "warehouse", "model_path", "series_path", "quality_report", "raw_data", "file",
})
MODEL_KEYS = frozenset({"random_forest", "extra_trees", "hist_gradient_boosting", "ridge", "seasonal_naive", "moving_average_7d"})
BACKTEST_COLUMNS = frozenset({"date", "fold", "stage", "actual", "comparable", "ml", *MODEL_KEYS})
FORECAST_COLUMNS = frozenset({"date", "prediction", "residual_band_low", "residual_band_high", "scheduled_open", "prediction_origin"})
METRIC_KEYS = frozenset({
    "schema_version", "series_sha256", "calendar", "freshness", "model_labels", "forecast_horizon_days",
    "source_days", "source_start", "source_end", "observed_target_days", "missing_target_days", "splits",
    "test_size_days", "evaluation_policy", "feature_policy", "promotion_gate", "targets", "calendar_review",
    "horizon_policy", "residual_band_policy",
})
TARGET_KEYS = frozenset({
    "selected_model", "candidate_models", "selection_folds", "holdout_folds", "selection_end", "holdout_start",
    "holdout_comparable_days", "holdout_gates_passed", "residual_band_sample_size", "folds", "test_days",
    "calendar_test_days", "excluded_comparison_days", "first_test_day", "last_test_day", "ml", "seasonal_naive",
    "moving_average_7d", "fold_wins", "mae_improvement_vs_seasonal", "mae_improvement_by_baseline",
    "baseline_gates_passed", "statistical_gate_passed", "operational_approved", "fold_details",
    "backtest_predictions", "experimental_forecast", "feature_importance", "feature_importance_kind", "monthly_projection",
})
MONTHLY_PROJECTION_KEYS = frozenset({"month", "forecast_origin", "start", "end", "horizon_from_origin_days", "bridge_days", "validation_policy", "predictions", "summary"})
MONTHLY_PREDICTION_COLUMNS = frozenset({"date", "prediction", "scheduled_open", "prediction_origin"})
MONTHLY_SUMMARY_KEYS = frozenset({"predicted_total", "predicted_open_days", "predicted_calendar_days"})
CALENDAR_KEYS = frozenset({"timezone", "open_weekdays", "opens_at", "closes_at", "confirmed_by_user_on", "historical_exceptions_validated", "policy"})
FRESHNESS_KEYS = frozenset({"as_of_date", "last_expected_complete_open_day", "days_since_source_end", "supports_current_week", "source_date_in_future"})
CALENDAR_REVIEW_KEYS = frozenset({"paid_orders_on_monday", "paid_orders_outside_reference_hours", "policy"})
FOLD_COLUMNS = frozenset({"fold", "stage", "train_end", "test_start", "test_end", "train_observed_days", "compared_days", "ml", *MODEL_KEYS})
BASELINE_KEYS = frozenset({"seasonal_naive", "moving_average_7d"})
FEATURE_NAMES = frozenset(FEATURE_COLUMNS) | {"missingindicator_" + name for name in FEATURE_COLUMNS}
PRIVATE_TEXT_PATTERNS = (
    re.compile(r"\b[A-Za-z]:[\\/]", re.IGNORECASE),
    re.compile(r"(?:data[\\/](?:private|raw|runs|processed|interim)|/(?:home|root|etc|users)/)", re.IGNORECASE),
    re.compile(r"\bhmac\.key\b", re.IGNORECASE),
)


def assert_no_private_fields(value: object) -> None:
    if isinstance(value, dict):
        if any(str(key).lower() in PRIVATE_FIELDS for key in value):
            raise ValueError("O pacote contém um campo privado ou uma referência a dados de origem.")
        for item in value.values():
            assert_no_private_fields(item)
    elif isinstance(value, list):
        for item in value:
            assert_no_private_fields(item)
    elif isinstance(value, str) and any(pattern.search(value) for pattern in PRIVATE_TEXT_PATTERNS):
        raise ValueError("O pacote contém uma referência a segredo ou caminho privado; revise sem publicar.")


def _only_keys(value: dict, allowed: frozenset | set, label: str) -> None:
    if not isinstance(value, dict) or set(value) - allowed:
        raise ValueError(f"Campos fora do contrato público: {label}.")


def _monthly_projection_contract(projection: dict, metrics: dict) -> None:
    _only_keys(projection, MONTHLY_PROJECTION_KEYS, "projeção mensal")
    if set(projection) != MONTHLY_PROJECTION_KEYS or not re.fullmatch(r"\d{4}-\d{2}", projection["month"]):
        raise ValueError("Projeção mensal incompleta ou mês inválido.")
    _only_keys(projection["summary"], MONTHLY_SUMMARY_KEYS, "resumo da projeção mensal")
    if set(projection["summary"]) != MONTHLY_SUMMARY_KEYS:
        raise ValueError("Resumo mensal incompleto.")
    year, month = map(int, projection["month"].split("-"))
    start = date(year, month, 1)
    end = date(year, month, monthrange(year, month)[1])
    origin = date.fromisoformat(projection["forecast_origin"])
    if origin.isoformat() != metrics["source_end"] or start <= origin or projection["start"] != start.isoformat() or projection["end"] != end.isoformat():
        raise ValueError("O mês projetado precisa ser posterior à origem real e conter o mês completo.")
    if projection["horizon_from_origin_days"] != (end - origin).days or projection["bridge_days"] != (start - origin).days - 1:
        raise ValueError("Distância temporal da projeção mensal inconsistente.")
    rows = projection["predictions"]
    if not isinstance(rows, list) or len(rows) != (end - start).days + 1:
        raise ValueError("A projeção mensal precisa ter uma estimativa para cada data do mês.")
    for offset, row in enumerate(rows):
        _only_keys(row, MONTHLY_PREDICTION_COLUMNS, "estimativa mensal")
        if set(row) != MONTHLY_PREDICTION_COLUMNS or row["date"] != (start + timedelta(days=offset)).isoformat():
            raise ValueError("Estimativa mensal incompleta ou datas fora de ordem.")
        if type(row["scheduled_open"]) is not bool or row["prediction_origin"] not in {"model", "calendar_closed"}:
            raise ValueError("Origem da estimativa mensal inválida.")
        if not isinstance(row["prediction"], (int, float)) or isinstance(row["prediction"], bool) or not math.isfinite(row["prediction"]) or row["prediction"] < 0:
            raise ValueError("Estimativa mensal precisa ser um número finito não negativo.")
        opened = date.fromisoformat(row["date"]).weekday() in metrics["calendar"]["open_weekdays"]
        if row["scheduled_open"] != opened or row["prediction_origin"] != ("model" if opened else "calendar_closed") or (not opened and row["prediction"] != 0):
            raise ValueError("Estimativa mensal não corresponde ao calendário informado.")
    summary = projection["summary"]
    if summary["predicted_calendar_days"] != len(rows) or summary["predicted_open_days"] != sum(row["scheduled_open"] for row in rows) or not math.isclose(summary["predicted_total"], sum(row["prediction"] for row in rows), rel_tol=1e-9, abs_tol=1e-7):
        raise ValueError("Resumo mensal não corresponde às estimativas diárias.")


def _metric_contract(metrics: dict) -> None:
    _only_keys(metrics["calendar"], CALENDAR_KEYS, "calendário")
    _only_keys(metrics["freshness"], FRESHNESS_KEYS, "atualidade")
    _only_keys(metrics["model_labels"], MODEL_KEYS - BASELINE_KEYS, "rótulos de modelos")
    if "calendar_review" in metrics:
        _only_keys(metrics["calendar_review"], CALENDAR_REVIEW_KEYS, "conferência do calendário")
    for result in metrics["targets"].values():
        _only_keys(result, TARGET_KEYS, "resultados do alvo")
        if result.get("selected_model") not in MODEL_KEYS - BASELINE_KEYS:
            raise ValueError("Modelo selecionado não autorizado.")
        _only_keys(result["candidate_models"], MODEL_KEYS, "candidatos")
        for scores in result["candidate_models"].values():
            _only_keys(scores, {"overall", "selection", "holdout"}, "etapas de avaliação")
            for score in scores.values():
                _only_keys(score, {"mae", "wape"}, "métricas")
        for name in ("ml", "seasonal_naive", "moving_average_7d"):
            _only_keys(result[name], {"mae", "wape"}, "métricas gerais")
        for name in ("fold_wins", "mae_improvement_by_baseline", "baseline_gates_passed", "holdout_gates_passed"):
            _only_keys(result[name], BASELINE_KEYS, "comparação com baselines")
        _only_keys(result["feature_importance"], FEATURE_NAMES, "pesos das variáveis")
        if "monthly_projection" in result:
            _monthly_projection_contract(result["monthly_projection"], metrics)
        for fold in result["fold_details"]:
            _only_keys(fold, FOLD_COLUMNS, "janela temporal")
            for name in ("ml", *MODEL_KEYS):
                _only_keys(fold[name], {"mae", "wape"}, "métricas da janela")


def sanitize_answers(answers: list[dict]) -> tuple[list[dict], int]:
    if not isinstance(answers, list) or [item.get("id") for item in answers] != list(range(1, 16)):
        raise ValueError("A geração precisa conter as 15 respostas agregadas.")
    clean = copy.deepcopy(answers)
    omitted = 0
    for answer in clean:
        if set(answer) != {"id", "question", "sql", "limitation", "results"} or not re.fullmatch(r"\d{2}_[a-z_]+\.sql", answer["sql"]):
            raise ValueError("Resposta fora do contrato público.")
        for index, rows in enumerate(answer["results"]):
            retained = []
            for row in rows:
                if not isinstance(row, dict) or set(row) - RESULT_COLUMNS:
                    raise ValueError("A resposta contém colunas não autorizadas para publicação.")
                # Remover toda a linha evita recuperar uma célula suprimida subtraindo partições.
                suppressed = any(row[key] is not None and float(row[key]) < MIN_GROUP for key in GROUP_COUNTS & row.keys())
                suppressed |= any(row[key] is not None and 0 < float(row[key]) < MIN_GROUP for key in CUSTOMER_PARTITIONS & row.keys())
                if suppressed:
                    omitted += 1
                else:
                    retained.append(row)
            answer["results"][index] = retained
        answer["limitation"] += " Publicação com recorte fixo: grupos pequenos são omitidos e não há filtros livres de datas."
    assert_no_private_fields(clean)
    return clean, omitted


def sanitize_metrics(metrics: dict, paid_orders_by_date: dict[str, float]) -> tuple[dict, int]:
    if metrics.get("schema_version") != 4 or set(metrics) - METRIC_KEYS:
        raise ValueError("A exportação pública exige o experimento ML atual (schema 4), sem campos adicionais.")
    clean = copy.deepcopy(metrics)
    if set(clean.get("targets", {})) != {"paid_orders", "total_received_brl"}:
        raise ValueError("Os alvos ML estão fora do contrato público.")
    _metric_contract(clean)
    omitted = 0
    for result in clean["targets"].values():
        retained = []
        for row in result["backtest_predictions"]:
            if set(row) - BACKTEST_COLUMNS:
                raise ValueError("Backtest contém campos não autorizados.")
            orders = paid_orders_by_date.get(row["date"], math.nan)
            if (math.isfinite(orders) and orders < MIN_GROUP) or (not math.isfinite(orders) and row["actual"] is not None):
                omitted += 1
            else:
                retained.append(row)
        result["backtest_predictions"] = retained
        if any(set(row) - FORECAST_COLUMNS for row in result["experimental_forecast"]):
            raise ValueError("Previsão contém campos não autorizados.")
    clean["public_display_policy"] = {
        "minimum_group_size": MIN_GROUP,
        "omitted_backtest_rows": omitted,
        "policy": "Linhas de teste com menos de cinco pedidos observados são omitidas na apresentação pública. Métricas agregadas continuam usando a avaliação privada completa; não podem ser recalculadas só pelas linhas exibidas. Previsões futuras são estimativas, não registros de clientes.",
    }
    assert_no_private_fields(clean)
    return clean, omitted


def render_public_report(answers: list[dict]) -> str:
    lines = ["# Jacaré Analytics — DEMONSTRAÇÃO SINTÉTICA", "", "Todos os valores, produtos, clientes e previsões deste pacote são fictícios e independentes do negócio real. Valor recebido não é lucro.", ""]
    for answer in answers:
        lines += [f"## {answer['id']}. {answer['question']}", "", answer_summary(answer), "", INTERPRETATIONS[answer["id"] - 1], "", answer["limitation"], "", f"Consulta reproduzível: `{answer['sql']}`.", ""]
        for rows in answer["results"]:
            if not rows:
                lines += ["Sem grupos elegíveis para publicação.", ""]
                continue
            headers = list(rows[0])
            lines += ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
            for row in rows:
                values = ["—" if row.get(key) is None else str(row[key]).replace("|", "\\|").replace("\n", " ") for key in headers]
                lines.append("| " + " | ".join(values) + " |")
            lines.append("")
    return "\n".join(lines) + "\n"


def export_public_snapshot(output: Path, *, project_root: Path = ROOT, business_approval: bool = False) -> dict:
    """Grava somente três artefatos permitidos e um manifesto, nunca aprova automaticamente."""
    if not isinstance(business_approval, bool):
        raise ValueError("A aprovação precisa ser uma decisão booleana explícita, não texto ou outro valor.")
    root, destination = project_root.resolve(), output.resolve()
    if destination == root or destination == root / "data" or destination.is_relative_to(root / "data/runs") or destination.is_relative_to(root / "data/private"):
        raise ValueError("Use um diretório separado e vazio para a exportação, não a geração privada.")
    if destination.exists() and (not destination.is_dir() or any(destination.iterdir())):
        raise ValueError("O destino precisa estar vazio; exportações existentes não são sobrescritas.")
    load_runtime_config(root, {"JACARE_PUBLIC_MODE": "true", "JACARE_PUBLIC_DATA_DIR": str(destination)})
    local = load_runtime_config(root, {"JACARE_PUBLIC_MODE": "false"})
    manifest = json.loads(local.current_manifest_path.read_text(encoding="utf-8"))
    if manifest.get("dataset_kind") != "synthetic":
        raise ValueError("Exportação pública de dados reais desabilitada, inclusive com aprovação. Execute python -m jacare_analytics.demo.")
    if manifest.get("schema_version") != 1 or manifest.get("quality", {}).get("all_passed") is not True or not all(value is True for value in manifest.get("quality", {}).get("checks", {}).values()):
        raise ValueError("A geração privada não possui qualidade aprovada.")
    report_path = local.resolve_artifact(manifest["analysis_report"])
    answers, omitted_answers = sanitize_answers(json.loads(report_path.with_name("analysis_results.json").read_text(encoding="utf-8")))
    metric_path = local.resolve_artifact(manifest["forecast_metrics"])
    series = metric_path.parents[1] / "processed/daily_sales_ml.csv"
    with series.open(encoding="utf-8", newline="") as handle:
        orders = {row["date"]: float(row["paid_orders"]) if row["paid_orders"].strip() else math.nan for row in csv.DictReader(handle)}
    public_metrics = json.loads(metric_path.read_text(encoding="utf-8"))
    # Estudo de desenvolvimento é privado e não integra o contrato da demo.
    public_metrics.pop('development_study', None)
    metrics, omitted_ml = sanitize_metrics(public_metrics, orders)
    quality = manifest["quality"]
    allowed_quality = {"checks", "all_passed", "paid_orders", "received_brl", "observed_days", "missing_days", "paid_orders_by_channel"}
    if set(quality) - allowed_quality:
        raise ValueError("Qualidade contém campos fora do contrato público.")
    public = {key: manifest[key] for key in ("schema_version", "run_id", "cutoff", "source_start", "source_end", "series_sha256", "dbt_models_built", "dbt_tests_passed")}
    public.update({
        "dataset_kind": "synthetic",
        "public_schema_version": 1, "publication_approved": bool(business_approval), "aggregation_only": True,
        "minimum_group_size": MIN_GROUP, "updated_at_utc": datetime.now(timezone.utc).isoformat(), "quality": quality,
        "analysis_results": "analysis/analysis_results.json", "analysis_report": "analysis/analysis_report.md",
        "forecast_metrics": "ml/forecast_metrics.json",
        "publication_policy": {"omitted_answer_rows": omitted_answers, "omitted_ml_rows": omitted_ml, "synthetic_only": True, "free_date_filters": False},
    })
    assert_no_private_fields(public)
    # Serializar antes de criar o destino: falhas de schema/NaN não deixam um pacote pela metade.
    contents = {
        "analysis/analysis_results.json": json.dumps(answers, ensure_ascii=False, allow_nan=False, indent=2).encode("utf-8"),
        "analysis/analysis_report.md": render_public_report(answers).encode("utf-8"),
        "ml/forecast_metrics.json": json.dumps(metrics, ensure_ascii=False, allow_nan=False, indent=2).encode("utf-8"),
    }
    public["artifact_sha256"] = {path: hashlib.sha256(content).hexdigest() for path, content in contents.items()}
    destination.mkdir(parents=True, exist_ok=True)
    for relative, content in contents.items():
        path = destination / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    (destination / "current_run.json").write_text(json.dumps(public, ensure_ascii=False, allow_nan=False, indent=2), encoding="utf-8")
    if business_approval:
        validate_public_manifest(public, load_runtime_config(root, {"JACARE_PUBLIC_MODE": "true", "JACARE_PUBLIC_DATA_DIR": str(destination)}))
    if {path.relative_to(destination).as_posix() for path in destination.rglob("*") if path.is_file()} != PUBLIC_ARTIFACTS | {"current_run.json"}:
        raise RuntimeError("O destino contém arquivos além do pacote permitido.")
    return public


def main() -> None:
    parser = argparse.ArgumentParser(description="Exporta somente uma geração sintética isolada. Use python -m jacare_analytics.demo; dados reais são bloqueados.")
    parser.add_argument("--output", type=Path, required=True, help="Diretório separado e vazio; mantenha fora do Git.")
    parser.add_argument("--business-approval", action="store_true", help="Usar APENAS depois de autorização expressa do responsável pelo negócio e revisão de privacidade.")
    args = parser.parse_args()
    result = export_public_snapshot(args.output, business_approval=args.business_approval)
    state = "aprovado por declaração explícita do operador" if result["publication_approved"] else "candidato NÃO aprovado para publicação"
    print(f"Pacote {state}: três artefatos agregados e um manifesto. Nenhum dado privado foi copiado.")


if __name__ == "__main__":
    main()
