"""Compara previsões congeladas com novas observações, sem reescrever o passado."""
import json

import duckdb
import pandas as pd
import streamlit as st


def compare_projection(projection,actual,target):
    """Pontua a previsão congelada nas mesmas datas realmente observadas."""
    predicted=pd.DataFrame(projection['predictions'])[['date','prediction']].copy()
    predicted['date']=pd.to_datetime(predicted.date)
    observed_field='paid_orders' if target=='paid_orders' else 'amount_received_brl'
    actual=actual.copy()
    actual['date']=pd.to_datetime(actual.date)
    observed=actual.loc[actual.has_source_records].dropna(subset=[observed_field])
    eligible=observed.loc[observed.paid_orders>=5]
    compared=predicted.merge(eligible[['date',observed_field]],on='date',how='inner').dropna()
    compared['error']=compared.prediction-compared[observed_field]
    denominator=compared[observed_field].abs().sum()
    result={
        'comparable_days':len(compared),'calendar_days':len(predicted),'observed_days':len(observed),
        'predicted_comparable':float(compared.prediction.sum()),
        'actual_comparable':float(compared[observed_field].sum()),
        'actual_observed_month':float(observed[observed_field].sum()),
        'mae':float(compared.error.abs().mean()) if len(compared) else None,
        'rmse':float((compared.error.pow(2).mean())**0.5) if len(compared) else None,
        'wape':float(compared.error.abs().sum()/denominator) if denominator else None,
        'bias_pct':float(compared.error.sum()/denominator) if denominator else None,
        'missing_scheduled_open_days':int(sum(row.get('scheduled_open',True) and pd.Timestamp(row['date']) not in set(observed.date) for row in projection['predictions'])),
    }
    chart=predicted.merge(eligible[['date',observed_field]],on='date',how='left').set_index('date').rename(columns={'prediction':'Previsão original',observed_field:'Realizado'})
    return result,compared,chart


def render_comparison(runtime,manifest):
    if runtime.public_mode: return
    archive=runtime.data_root/"forecast_archive"
    if not archive.is_dir(): return
    files=sorted(path for path in archive.glob("*.json") if not path.is_symlink())
    snapshots=[]
    for file in files:
        saved=json.loads(file.read_text(encoding="utf-8"))
        metrics=saved["metrics"]
        # Arquivo local protegido; hash e origem preservados pelo worker.
        if metrics["source_end"]!=saved["source_end"]: raise ValueError("Arquivo de previsão divergente")
        snapshots.append(saved)
    if not snapshots: return
    snapshots.sort(key=lambda entry:entry['source_end'])
    st.subheader("Previsão original × realizado após a atualização")
    index=st.selectbox("Origem da previsão preservada",list(range(len(snapshots))),format_func=lambda index:snapshots[index]["source_end"],key="frozen_forecast_origin")
    snapshot=snapshots[index]
    metrics=snapshot["metrics"]
    label={"paid_orders":"Pedidos pagos","total_received_brl":"Valor recebido (R$)"}
    target=st.selectbox("Indicador para comparar",list(label),format_func=label.get,key="frozen_forecast_target")
    projection=metrics["targets"][target]["monthly_projection"]
    predicted=pd.DataFrame(projection["predictions"])[["date","prediction"]]
    predicted["date"]=pd.to_datetime(predicted.date)
    with duckdb.connect(str(runtime.project_root/manifest["warehouse"]),read_only=True) as connection:
        actual=connection.execute("select sale_date as date,paid_orders,amount_received_brl,has_source_records from analytics.fct_daily_sales where sale_date between ? and ? order by 1",[projection["start"],projection["end"]]).df()
    st.caption(f"Estimativa do mês {projection['month']}, calculada com dados até {snapshot['source_end']}. Esta previsão foi preservada; o treinamento novo não altera seus valores. A comparação é retrospectiva e não aprova o modelo para uso operacional.")
    if actual.empty:
        st.info("Ainda não há dados realizados desse mês. A previsão original está preservada para comparar quando o pacote atualizado for aprovado.")
        return
    observed_field="paid_orders" if target=="paid_orders" else "amount_received_brl"
    result,compared,chart=compare_projection(projection,actual,target)
    if len(compared)<7:
        st.info("Menos de sete dias observados elegíveis para comparar; envie mais dados completos. Não preenchemos dias ausentes com zero.")
        return
    cols=st.columns(3)
    format_value=(lambda value:"R$ "+f"{value:,.2f}".replace(",","X").replace(".",",").replace("X",".")) if target!="paid_orders" else (lambda value:f"{value:,.1f}".replace(",","X").replace(".",",").replace("X","."))
    cols[0].metric("Previsto nos dias comparáveis",format_value(compared.prediction.sum()))
    cols[1].metric("Realizado nos mesmos dias",format_value(compared[observed_field].sum()))
    cols[2].metric("Erro absoluto médio por dia",format_value((compared.prediction-compared[observed_field]).abs().mean()))
    scores=st.columns(3)
    scores[0].metric('Erro percentual ponderado (WAPE)',f"{result['wape']:.1%}" if result['wape'] is not None else 'Não calculável')
    scores[1].metric('Viés do total previsto',f"{result['bias_pct']:+.1%}" if result['bias_pct'] is not None else 'Não calculável')
    scores[2].metric('Erro que penaliza grandes desvios (RMSE)',format_value(result['rmse']))
    st.caption('MAE é o tamanho médio do erro diário. WAPE soma os erros absolutos e divide pelo realizado: menor é melhor, mas não é uma taxa de acerto. Viés negativo significa que o total foi subestimado; positivo, superestimado. RMSE dá mais peso aos dias com erros grandes. Nenhuma dessas métricas transforma a projeção mensal experimental em garantia.')
    st.line_chart(chart,color=["#1674d1","#159c94"])
    st.caption(f"Comparação em {len(compared)} dias elegíveis de {len(predicted)} dias de calendário da previsão. Datas ausentes ou com menos de cinco pedidos não são comparadas nem tratadas como venda zero. Totais acima são só dos mesmos dias comparáveis, não necessariamente do mês completo.")
    selected=metrics['targets'][target]['selected_model']
    st.write('Modelo da previsão preservada: '+metrics.get('model_labels',{}).get(selected,selected)+'. O modelo usou somente o histórico até a origem indicada e avançou recursivamente até o mês projetado. O novo treinamento usa o histórico atualizado, mas não reescreve esta previsão.')
    st.caption('A origem é o último dia de dados de treino, não necessariamente a data em que a previsão foi emitida. A comparação usa dados que não estavam no treinamento original, porém não comprova que a previsão foi publicada antes do início do mês.')
    if result['missing_scheduled_open_days']:
        st.warning(f"Faltam registros em {result['missing_scheduled_open_days']} dias de abertura planejada. Não presumimos venda zero nesses dias; confirme se houve fechamento, ausência de vendas ou falha na captura.")
    with st.expander('Conferir comparação por semana e por dia'):
        compared['week_start']=compared.date-pd.to_timedelta(compared.date.dt.dayofweek,unit='D')
        weekly=compared.groupby('week_start').agg(predicted=('prediction','sum'),actual=(observed_field,'sum'),days=('date','count')).reset_index()
        st.dataframe(weekly.rename(columns={'week_start':'Início da semana','predicted':'Previsto','actual':'Realizado','days':'Dias comparáveis'}),hide_index=True)
        st.caption('Semanas de borda podem ser parciais; cada linha inclui somente os mesmos dias comparáveis.')
        st.dataframe(compared[['date','prediction',observed_field,'error']].rename(columns={'date':'Data','prediction':'Previsto',observed_field:'Realizado','error':'Previsto menos realizado'}),hide_index=True)
