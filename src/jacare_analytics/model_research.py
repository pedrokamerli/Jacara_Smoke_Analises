"""Estudo versionado de engenharia de atributos, sem substituir o modelo vigente."""
import math
from datetime import timedelta
from sklearn.model_selection import TimeSeriesSplit
from threadpoolctl import threadpool_limits
from .forecast_backtest import _features, _model, _read_series, _score
from .business_calendar import is_open

VARIANTS = {'extra_trees_calendar':'Extra Trees + calendário cíclico', 'ridge_calendar':'Ridge + calendário cíclico'}


def calendar_features(history, day):
    # Só há observações anteriores à origem; não acessa o alvo do próprio dia.
    known = [history[-lag] for lag in (7, 14, 21, 28) if math.isfinite(history[-lag])]
    weekday_mean = sum(known)/len(known) if known else math.nan
    return _features(history, day) + [math.sin(2*math.pi*day.weekday()/7), math.cos(2*math.pi*day.weekday()/7), weekday_mean, float(len(known))]


def recursive(model, history, first, horizon, calendar):
    rolling = history.copy()
    output = []
    for offset in range(horizon):
        day = first+timedelta(days=offset)
        value = max(0., float(model.predict([calendar_features(rolling, day)])[0])) if is_open(day, calendar) else 0.
        if not math.isfinite(value):
            raise ValueError('Pesquisa gerou previsão não finita')
        output.append(value)
        rolling.append(value)
    return output


def study(series_path, current):
    dates, targets = _read_series(series_path)
    calendar = current['calendar']
    result = {'version':'calendar-features-v1', 'production_model_changed':False,
              'policy':'Pesquisa retrospectiva: adicionamos dia da semana cíclico e média das quatro ocorrências anteriores do mesmo dia. Comparamos Extra Trees e Ridge com o modelo vigente nas mesmas datas. Escolhemos a variante pelas seis janelas de seleção, antes das duas finais. Como o período final já foi examinado no desenvolvimento anterior, ele NÃO é uma nova validação independente. A pesquisa não troca automaticamente o modelo de produção; exige acompanhamento com novos dados.', 'targets':{}}
    with threadpool_limits(limits=1):
        for target, values in targets.items():
            original = current['targets'][target]
            features = [calendar_features(values[:i], dates[i]) for i in range(28, len(values))]
            forecasts = {name:[] for name in VARIANTS}
            for fold, (train, test) in enumerate(TimeSeriesSplit(n_splits=current['splits'], test_size=7).split(features), start=1):
                eligible = [int(i) for i in train if math.isfinite(values[int(i)+28])]
                origin = int(test[0])+28
                for name in VARIANTS:
                    model = _model(name.removesuffix('_calendar')).fit([features[i] for i in eligible], [values[i+28] for i in eligible])
                    estimates = recursive(model, values[:origin], dates[origin], 7, calendar)
                    forecasts[name].extend(estimates)
            rows = original['backtest_predictions']
            def score(name, stage):
                positions = [i for i, row in enumerate(rows) if row['comparable'] and row['stage']==stage]
                return _score([rows[i]['actual'] for i in positions], [forecasts[name][i] for i in positions])
            selected = min(VARIANTS, key=lambda name:(score(name, 'selection')['mae'], name))
            summary = []
            base = original['candidate_models'][original['selected_model']]
            summary.append({'Abordagem':'Modelo vigente (atributos originais)', 'Erro seleção':base['selection']['mae'], 'Erro final retrospectivo':base['holdout']['mae'], 'Papel':'Referência congelada'})
            for name, label in VARIANTS.items():
                summary.append({'Abordagem':label, 'Erro seleção':score(name, 'selection')['mae'], 'Erro final retrospectivo':score(name, 'holdout')['mae'], 'Papel':'Variante escolhida antes do teste' if name==selected else 'Variante candidata'})
            improvement = 1-score(selected, 'holdout')['mae']/base['holdout']['mae'] if base['holdout']['mae'] else None
            text = ('menos' if improvement is not None and improvement>0 else 'mais')
            conclusion = f"A variante escolhida ({VARIANTS[selected]}) teve {abs(improvement):.1%} {text} erro diário que o modelo vigente no período final já conhecido." if improvement is not None else 'Não foi possível calcular a redução relativa do erro.'
            conclusion += ' Isso descreve esta amostra, não garante ganho futuro. Preservamos o modelo e a previsão originais; a próxima avaliação deve usar dados ainda não examinados.'
            result['targets'][target] = {'selected_variant':selected, 'summary':summary, 'holdout_mae_improvement':improvement, 'conclusion':conclusion, 'compared_days':original['holdout_comparable_days']}
    return result
