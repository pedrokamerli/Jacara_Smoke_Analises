"""Experimento temporal reproduzível: alvos ausentes nunca são inventados."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import joblib
import numpy as np
from sklearn.ensemble import RandomForestRegressor, ExtraTreesRegressor, HistGradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.model_selection import TimeSeriesSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from threadpoolctl import threadpool_limits

from .business_calendar import load_calendar, is_open, freshness

DEFAULT_OUTPUT = Path("data/interim/forecast_backtest.md")
FEATURE_COLUMNS = ("weekday", "day_of_month", "month", "lag_1", "lag_7", "lag_14", "lag_28", "rolling_mean_7", "rolling_mean_28", "observed_days_7", "observed_days_28")
MODEL_LABELS = {"random_forest":"Random Forest", "extra_trees":"Extra Trees", "hist_gradient_boosting":"Hist Gradient Boosting", "ridge":"Regressão Ridge"}
BASELINES = ("seasonal_naive", "moving_average_7d")


def _read_series(path: Path) -> tuple[list[date], dict[str, list[float]]]:
    dates: list[date] = []
    targets: dict[str, list[float]] = {"paid_orders": [], "total_received_brl": []}
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or not {"date", *targets}.issubset(reader.fieldnames):
            raise ValueError("A série precisa conter date, paid_orders e total_received_brl.")
        for row in reader:
            dates.append(date.fromisoformat(row["date"]))
            for name in targets:
                value = float(row[name]) if row[name].strip() else math.nan
                if math.isinf(value):
                    raise ValueError("Há valor infinito na série temporal.")
                targets[name].append(value)
    if len(dates) < 90 or any(dates[i] - dates[i - 1] != timedelta(days=1) for i in range(1, len(dates))):
        raise ValueError("O experimento exige ao menos 90 datas de calendário, consecutivas; alvos podem estar ausentes.")
    return dates, targets


def _observed_mean(values: list[float]) -> float:
    known = [value for value in values if math.isfinite(value)]
    return sum(known) / len(known) if known else math.nan


def _features(history: list[float], target_date: date) -> list[float]:
    return [float(target_date.weekday()), float(target_date.day), float(target_date.month), history[-1], history[-7], history[-14], history[-28], _observed_mean(history[-7:]), _observed_mean(history[-28:]), float(sum(math.isfinite(v) for v in history[-7:])), float(sum(math.isfinite(v) for v in history[-28:]))]


def _model(name: str = "random_forest") -> Pipeline:
    # Imputação somente de features e ajustada somente no treino de cada janela.
    estimators = {
        "random_forest": RandomForestRegressor(n_estimators=120, max_depth=6, min_samples_leaf=5, max_features=0.8, random_state=42, n_jobs=1),
        "extra_trees": ExtraTreesRegressor(n_estimators=160, max_depth=6, min_samples_leaf=5, max_features=0.8, random_state=42, n_jobs=1),
        "hist_gradient_boosting": HistGradientBoostingRegressor(max_iter=120, learning_rate=0.05, max_leaf_nodes=15, min_samples_leaf=10, l2_regularization=1.0, early_stopping=False, random_state=42),
        "ridge": Ridge(alpha=10.0),
    }
    if name not in estimators:
        raise ValueError("Modelo fora da lista de candidatos do experimento.")
    steps = [("imputer", SimpleImputer(strategy="median", add_indicator=True, keep_empty_features=True))]
    if name == "ridge":
        steps.append(("scaler", StandardScaler()))
    return Pipeline(steps + [("estimator",estimators[name])])


def _forecast(model: Pipeline, history: list[float], first_date: date, horizon: int, calendar: dict | None = None) -> list[float]:
    if len(history) < 28 or horizon < 1:
        raise ValueError("A previsão exige pelo menos 28 datas anteriores e horizonte positivo.")
    rolling = history.copy()
    predictions = []
    for offset in range(horizon):
        day = first_date + timedelta(days=offset)
        value = 0.0 if calendar and not is_open(day,calendar) else max(0.0, float(model.predict([_features(rolling, day)])[0]))
        if not math.isfinite(value):
            raise ValueError("O modelo gerou uma estimativa não finita.")
        rolling.append(value)
        predictions.append(value)
    return predictions


def _score(actual: list[float], predicted: list[float]) -> dict[str, float | None]:
    if len(actual) != len(predicted):
        raise ValueError("Realizados e estimativas precisam ter o mesmo número de observações.")
    if not actual:
        return {"mae": None, "wape": None}
    errors = [abs(a - p) for a, p in zip(actual, predicted)]
    denominator = sum(abs(value) for value in actual)
    return {"mae": sum(errors) / len(errors), "wape": sum(errors) / denominator if denominator else None}


def _monthly_projection(model: Pipeline, history: list[float], source_end: date, calendar: dict) -> dict[str, Any]:
    """Projeta o próximo mês completo sem pular os dias até o início dele."""
    start = date(source_end.year + (source_end.month == 12), source_end.month % 12 + 1, 1)
    following = date(start.year + (start.month == 12), start.month % 12 + 1, 1)
    end = following - timedelta(days=1)
    first_forecast = source_end + timedelta(days=1)
    bridge_days = (start - first_forecast).days
    horizon = (end - source_end).days
    # Os lags e médias do mês projetado incluem as estimativas da ponte,
    # nunca valores realizados que não eram conhecidos na origem.
    estimates = _forecast(model, history, first_forecast, horizon, calendar)
    predictions = []
    for offset, estimate in enumerate(estimates[bridge_days:], start=bridge_days):
        day = first_forecast + timedelta(days=offset)
        opened = is_open(day, calendar)
        predictions.append({"date": day.isoformat(), "prediction": estimate, "scheduled_open": opened, "prediction_origin": "model" if opened else "calendar_closed"})
    return {
        "month": start.strftime("%Y-%m"),
        "forecast_origin": source_end.isoformat(),
        "start": start.isoformat(),
        "end": end.isoformat(),
        "horizon_from_origin_days": horizon,
        "bridge_days": bridge_days,
        "validation_policy": "Projeção mensal exploratória a partir da última data real da fonte. A recursão percorre todos os dias intermediários antes do mês projetado, sem acessar realizados posteriores à origem. O backtest valida sete dias, não este horizonte mensal; erros podem se acumular. Não há intervalo mensal calibrado nem aprovação operacional. A projeção não é faturamento realizado nem previsão atual reoriginada na data de consulta.",
        "predictions": predictions,
        "summary": {
            "predicted_total": sum(row["prediction"] for row in predictions),
            "predicted_open_days": sum(row["scheduled_open"] for row in predictions),
            "predicted_calendar_days": len(predictions),
        },
    }


def _evaluate_target(dates: list[date], values: list[float], *, n_splits: int, test_size: int, calendar: dict) -> tuple[dict[str, Any], dict[str, Pipeline]]:
    features = [_features(values[:index], dates[index]) for index in range(28, len(values))]
    labels = values[28:]
    splitter = TimeSeriesSplit(n_splits=n_splits, test_size=test_size)
    if n_splits < 4:
        raise ValueError("São necessárias pelo menos duas janelas para seleção e duas para teste final.")
    selection_folds = n_splits - 2
    estimators = (*MODEL_LABELS,*BASELINES)
    folds = []
    predictions = []
    selected = None
    for fold, (train, test) in enumerate(splitter.split(features), start=1):
        origin = int(test[0]) + 28
        eligible_train = [int(position) for position in train if math.isfinite(labels[position])]
        if len(eligible_train) < 30:
            raise ValueError("Há menos de 30 alvos observados em uma janela de treino.")
        # A escolha fica congelada ANTES de observar as duas janelas finais.
        if fold == selection_folds + 1:
            chosen_scores = {name: _prediction_score(predictions,name) for name in MODEL_LABELS}
            selected = min(MODEL_LABELS,key=lambda name:(chosen_scores[name]["mae"],name))
        outputs = {}
        for name in MODEL_LABELS:
            model = _model(name).fit([features[i] for i in eligible_train], [labels[i] for i in eligible_train])
            outputs[name] = _forecast(model, values[:origin], dates[origin], test_size,calendar)
        outputs["seasonal_naive"] = [values[origin + offset - 7] if is_open(dates[origin+offset],calendar) else 0.0 for offset in range(test_size)]
        outputs["moving_average_7d"] = [_observed_mean(values[origin - 7:origin]) if is_open(dates[origin+offset],calendar) else 0.0 for offset in range(test_size)]
        window_rows = []
        for offset in range(test_size):
            actual = values[origin + offset]
            comparable = math.isfinite(actual) and all(math.isfinite(outputs[name][offset]) for name in estimators)
            row = {"date":dates[origin+offset].isoformat(), "fold":fold, "stage":"selection" if fold<=selection_folds else "holdout", "actual":actual if math.isfinite(actual) else None, "comparable":comparable}
            row.update({name: output[offset] if math.isfinite(output[offset]) else None for name,output in outputs.items()})
            window_rows.append(row)
        predictions.extend(window_rows)
        scores = {name:_prediction_score(window_rows,name) for name in estimators}
        if not any(row["comparable"] for row in window_rows):
            raise ValueError("Uma janela não tem alvos observados comparáveis aos baselines.")
        folds.append({"fold":fold, "stage":"selection" if fold<=selection_folds else "holdout", "train_end":dates[origin-1].isoformat(), "test_start":dates[origin].isoformat(), "test_end":dates[origin+test_size-1].isoformat(), "train_observed_days":len(eligible_train), "compared_days":sum(row["comparable"] for row in window_rows), **scores})
    candidates = {name:{"overall":_prediction_score(predictions,name), "selection":_prediction_score(predictions,name,"selection"), "holdout":_prediction_score(predictions,name,"holdout")} for name in estimators}
    for row in predictions:
        row["ml"] = row[selected]
    for fold in folds:
        fold["ml"] = fold[selected]
    scores = {"ml":candidates[selected]["overall"], **{key:candidates[key]["overall"] for key in BASELINES}}
    wins = {baseline:sum(fold["ml"]["mae"] < fold[baseline]["mae"] for fold in folds) for baseline in BASELINES}
    improvements = {baseline: 1 - scores["ml"]["mae"] / scores[baseline]["mae"] if scores[baseline]["mae"] else None for baseline in wins}
    baseline_gates = {baseline: gain is not None and gain >= 0.10 and wins[baseline] / len(folds) >= 0.75 for baseline, gain in improvements.items()}
    comparable = [row for row in predictions if row["comparable"]]
    holdout = [row for row in comparable if row["stage"]=="holdout"]
    holdout_gates = {baseline:candidates[selected]["holdout"]["mae"] < candidates[baseline]["holdout"]["mae"] for baseline in BASELINES}
    passes = all(baseline_gates.values()) and len(comparable)>=28 and len(holdout)>=10 and all(holdout_gates.values())
    training = [i for i, value in enumerate(labels) if math.isfinite(value)]
    fitted_models = {name:_model(name).fit([features[i] for i in training],[labels[i] for i in training]) for name in MODEL_LABELS}
    fitted = fitted_models[selected]
    future = _forecast(fitted, values, dates[-1] + timedelta(days=1), 14,calendar)
    # Somente os erros finais, não as janelas usadas para escolher o algoritmo.
    residuals = np.array([row["actual"]-row["ml"] for row in holdout])
    if not len(residuals):
        raise ValueError("Não há observações comparáveis no teste final para estimar a faixa exploratória.")
    low, high = np.quantile(residuals, [0.10, 0.90])
    forecast_rows = []
    for offset,value in enumerate(future):
        day = dates[-1]+timedelta(days=offset+1)
        opened = is_open(day,calendar)
        forecast_rows.append({"date":day.isoformat(), "prediction":value, "residual_band_low":max(0.0,value+float(low)) if opened else 0.0, "residual_band_high":max(0.0,value+float(high)) if opened else 0.0, "scheduled_open":opened, "prediction_origin":"model" if opened else "calendar_closed"})
    names = fitted.named_steps["imputer"].get_feature_names_out(FEATURE_COLUMNS)
    estimator = fitted.named_steps["estimator"]
    weights = getattr(estimator,"feature_importances_",None)
    importance_kind = "tree_importance"
    if weights is None and hasattr(estimator,"coef_"):
        weights = np.abs(estimator.coef_)
        weights = weights/weights.sum() if weights.sum() else weights
        importance_kind = "absolute_standardized_coefficients"
    importance = dict(zip(names,[float(v) for v in weights])) if weights is not None else {}
    return {
        "selected_model":selected, "candidate_models":candidates, "selection_folds":selection_folds, "holdout_folds":2,
        "selection_end":folds[selection_folds-1]["test_end"], "holdout_start":folds[selection_folds]["test_start"],
        "holdout_comparable_days":len(holdout), "holdout_gates_passed":holdout_gates,
        "residual_band_sample_size":len(residuals),
        "folds": len(folds), "test_days": len(comparable), "calendar_test_days": n_splits * test_size,
        "excluded_comparison_days": n_splits * test_size - len(comparable),
        "first_test_day": folds[0]["test_start"], "last_test_day": folds[-1]["test_end"],
        **scores, "fold_wins": wins, "mae_improvement_vs_seasonal": improvements["seasonal_naive"],
        "mae_improvement_by_baseline": improvements, "baseline_gates_passed": baseline_gates,
        "statistical_gate_passed": bool(passes), "operational_approved": False,
        "fold_details": folds, "backtest_predictions": predictions,
        "experimental_forecast": forecast_rows, "feature_importance": importance, "feature_importance_kind":importance_kind,
        "monthly_projection": _monthly_projection(fitted, values, dates[-1], calendar),
    }, fitted_models


def _prediction_score(rows: list[dict], name: str, stage: str | None = None) -> dict:
    comparable = [row for row in rows if row["comparable"] and (stage is None or row["stage"]==stage)]
    return _score([row["actual"] for row in comparable],[row[name] for row in comparable])


def _experiment(series_path: Path, n_splits: int, test_size: int, calendar: dict | None = None) -> tuple[dict[str, Any], dict]:
    if test_size != 7:
        raise ValueError("O contrato atual do experimento usa horizonte de sete dias.")
    dates, targets = _read_series(series_path)
    calendar = calendar or load_calendar()
    results = {}
    models = {}
    with threadpool_limits(limits=1):
        for target, values in targets.items():
            results[target], models[target] = _evaluate_target(dates, values, n_splits=n_splits, test_size=test_size,calendar=calendar)
    return {
        "schema_version": 4, "series_sha256": hashlib.sha256(series_path.read_bytes()).hexdigest(),
        "calendar":calendar, "freshness":freshness(dates[-1],calendar), "model_labels":MODEL_LABELS, "forecast_horizon_days":14,
        "source_days": len(dates), "source_start": dates[0].isoformat(), "source_end": dates[-1].isoformat(),
        "observed_target_days": sum(math.isfinite(value) for value in targets["paid_orders"]),
        "missing_target_days": sum(not math.isfinite(value) for value in targets["paid_orders"]),
        "splits": n_splits, "test_size_days": test_size,
        "evaluation_policy": f"Quatro algoritmos e dois baselines usam as mesmas datas observadas. O algoritmo ML é escolhido nas {n_splits-2} primeiras janelas pelo menor MAE; a escolha fica congelada antes das duas janelas finais. Resultados finais não são usados para trocar o algoritmo. Métricas gerais incluem as janelas de seleção e são diagnósticas; a evidência final é apresentada separadamente. O calendário informado orienta as estimativas, não preenche alvos históricos.",
        "feature_policy": "Lags ausentes usam imputação por mediana aprendida somente no treino e indicadores de ausência; nenhuma observação de venda é preenchida. Na recursão futura, lags, médias e contagens de valores disponíveis passam a incluir estimativas anteriores, não novas vendas observadas.",
        "promotion_gate": "Contra cada baseline: redução de MAE >= 10%, vitória em >= 75% das janelas e >= 28 dias comparáveis; também menor MAE nos dois testes finais agregados, com >= 10 dias comparáveis. Uso operacional exige histórico atual e validação das exceções ao calendário.",
        "horizon_policy": "O backtest compara previsões de sete dias. As estimativas de oito a quatorze dias são uma extensão recursiva ainda não validada em horizonte próprio; seus erros podem acumular.",
        "residual_band_policy": "Faixa exploratória: percentis 10 e 90 dos poucos erros do teste final de sete dias. Não é intervalo calibrado, não garante cobertura e não foi validada para o horizonte de quatorze dias.",
        "targets": results,
    }, models


def run_backtest_metrics(series_path: Path, n_splits: int = 8, test_size: int = 7) -> dict[str, Any]:
    return _experiment(series_path, n_splits, test_size)[0]


def render_backtest_report(metrics: dict[str, Any]) -> str:
    calendar = metrics["calendar"]
    freshness_info = metrics["freshness"]
    labels = {**metrics["model_labels"], "seasonal_naive": "Mesmo dia da semana anterior", "moving_average_7d": "Média observada dos 7 dias anteriores"}
    target_labels = {"paid_orders": "Pedidos pagos (pedidos/dia)", "total_received_brl": "Valor recebido (R$/dia)"}
    first_forecast = date.fromisoformat(metrics["source_end"]) + timedelta(days=1)
    last_forecast = first_forecast + timedelta(days=metrics["forecast_horizon_days"] - 1)
    lines = [
        "# Avaliação temporal de demanda", "",
        f"Fonte real: {metrics['source_start']} a {metrics['source_end']}. {metrics['observed_target_days']} dias observados e {metrics['missing_target_days']} datas sem alvo.", "",
        f"Calendário de referência informado: terça a domingo, {calendar['opens_at']} às {calendar['closes_at']}, fuso {calendar['timezone']}. Exceções históricas validadas: {'sim' if calendar.get('historical_exceptions_validated') else 'não'}.", "",
        "Segundas-feiras futuras recebem estimativa zero por fechamento planejado. Isso não transforma lacunas ou pedidos históricos em zero, não descarta registros fora do horário e não comprova que a loja esteve fechada em todas as segundas anteriores.", "",
        f"Atualidade verificada em {freshness_info['as_of_date']}: fonte encerrada há {freshness_info['days_since_source_end']} dias. " + ("A data da fonte alcança o último dia completo esperado pelo calendário; isso não comprova captura completa." if freshness_info['supports_current_week'] else "A fonte não sustenta uma previsão para a semana atual."), "",
        metrics["evaluation_policy"], "", metrics["feature_policy"], "",
        "MAE é o tamanho médio do erro na unidade do alvo; menor é melhor. WAPE compara a soma dos erros absolutos com o volume realizado. Todos os candidatos são pontuados nas mesmas datas, sem inventar vendas ausentes.", "",
    ]
    for target, result in metrics["targets"].items():
        selected = result["selected_model"]
        lines.extend([
            f"## {target_labels.get(target, target)}", "",
            f"Algoritmo ML escolhido: {labels[selected]}, pelas {result['selection_folds']} primeiras janelas encerradas em {result['selection_end']}. A escolha foi congelada antes dos {result['holdout_folds']} testes finais, iniciados em {result['holdout_start']} ({result['holdout_comparable_days']} dias observados comparáveis).", "",
            "| Abordagem | MAE seleção | MAE teste final | WAPE teste final | MAE geral (diagnóstico) |", "|---|---:|---:|---:|---:|",
        ])
        for name, scores in result["candidate_models"].items():
            wape = scores["holdout"]["wape"]
            wape_text = f"{wape:.1%}" if wape is not None else "Não calculável"
            label = labels[name] + (" — ML escolhido" if name == selected else "")
            lines.append(f"| {label} | {scores['selection']['mae']:.2f} | {scores['holdout']['mae']:.2f} | {wape_text} | {scores['overall']['mae']:.2f} |")
        lines.extend([
            "",
            f"Critério estatístico combinado: {'atingido' if result['statistical_gate_passed'] else 'não atingido'}. Vitórias gerais contra sazonal: {result['fold_wins']['seasonal_naive']}/{result['folds']}; contra média: {result['fold_wins']['moving_average_7d']}/{result['folds']}. Esses totais incluem seleção, não são uma validação independente.", "",
            "No teste final agregado, o modelo escolhido supera o baseline sazonal: " + ("sim" if result["holdout_gates_passed"]["seasonal_naive"] else "não") + "; supera a média: " + ("sim" if result["holdout_gates_passed"]["moving_average_7d"] else "não") + ".", "",
            f"Faixa exploratória baseada em somente {result['residual_band_sample_size']} resíduos finais. Aprovação operacional: não; nenhuma compra de estoque ou decisão automática é acionada.", "",
        ])
        projection = result["monthly_projection"]
        summary = projection["summary"]
        total_text = f"{summary['predicted_total']:.2f}" if target == "total_received_brl" else f"{summary['predicted_total']:.1f}"
        unit = "R$" if target == "total_received_brl" else "pedidos estimados"
        lines.extend([
            f"### Projeção do mês {projection['month']}", "",
            f"Total projetado: {total_text} {unit}, em {summary['predicted_calendar_days']} dias de calendário e {summary['predicted_open_days']} dias de abertura planejada. Origem do modelo: {projection['forecast_origin']}. Janela mensal: {projection['start']} a {projection['end']}.", "",
            f"A recursão começa no dia seguinte à origem e percorre {projection['bridge_days']} dias de ponte antes do mês. O último dia mensal está a {projection['horizon_from_origin_days']} dias da origem. Não há faixas de confiança mensais inventadas.", "",
            projection["validation_policy"], "",
        ])
    lines.extend(["## Limites de uso", "", metrics["promotion_gate"], "", metrics["horizon_policy"], "", metrics["residual_band_policy"], "", f"As estimativas são para os {metrics['forecast_horizon_days']} dias após a última data real da fonte, com opção de consultar os primeiros sete: {first_forecast:%d/%m/%Y} a {last_forecast:%d/%m/%Y}. " + ("Esta janela não é uma previsão atual: a fonte está desatualizada. " if not freshness_info["supports_current_week"] else "A proximidade da fonte não comprova captura completa nem aprovação operacional. ") + "Previsão é estimativa, não observação nem promessa de resultado."])
    return "\n".join(lines) + "\n"


def save_experiment(series_path: Path, output_dir: Path, calendar: dict | None = None) -> dict[str, Any]:
    metrics, models = _experiment(series_path, 8, 7,calendar)
    from .model_research import study
    metrics['development_study'] = study(series_path, metrics)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "forecast_metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    (output_dir / "forecast_backtest.md").write_text(render_backtest_report(metrics), encoding="utf-8")
    joblib.dump({"models":{target:candidates[metrics['targets'][target]['selected_model']] for target,candidates in models.items()}, "candidate_models":models, "calendar":metrics["calendar"], "feature_columns": FEATURE_COLUMNS, "series_sha256": metrics["series_sha256"]}, output_dir / "forecast_models.joblib")
    return metrics


def run_backtest(series_path: Path, n_splits: int = 8, test_size: int = 7) -> str:
    return render_backtest_report(run_backtest_metrics(series_path, n_splits, test_size))


def main() -> None:
    parser = argparse.ArgumentParser(description="Compara quatro modelos e dois baselines, com seleção temporal e teste final, sem inventar alvos ausentes.")
    parser.add_argument("--series", type=Path, help="CSV explícito; sem esta opção, usa a série da geração ativa.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--metrics-output", type=Path, default=Path("data/interim/forecast_metrics.json"))
    args = parser.parse_args()
    if args.series is None:
        project_root = Path(__file__).resolve().parents[2]
        current = project_root / "data/current_run.json"
        if not current.exists():
            parser.error("Importe as fontes reais pelo pipeline ou informe --series. Não há geração ativa.")
        manifest = json.loads(current.read_text(encoding="utf-8"))
        args.series = (project_root / manifest["warehouse"]).resolve().parent / "processed/daily_sales_ml.csv"
        if not args.series.is_relative_to(project_root / "data/runs"):
            parser.error("A série da geração ativa está fora do diretório de dados autorizado.")
    metrics = save_experiment(args.series, args.metrics_output.parent)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render_backtest_report(metrics), encoding="utf-8")
    if args.metrics_output.name != "forecast_metrics.json":
        args.metrics_output.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Experimento salvo: métricas, backtest e modelos locais; nenhum alvo ausente foi preenchido.")


if __name__ == "__main__":
    main()
