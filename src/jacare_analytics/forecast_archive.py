"""Compara previsões congeladas com novas observações, sem reescrever o passado."""
import json

import duckdb
import pandas as pd
import streamlit as st


def render_comparison(runtime,manifest):
    if runtime.public_mode: return
    archive=runtime.data_root/"forecast_archive"
    if not archive.is_dir(): return
    files=sorted(path for path in archive.glob("*.json") if not path.is_symlink())
    snapshots=[]
    for file in files:
        saved=json.loads(file.read_text(encoding="utf-8"))
        metrics=saved["metrics"]
        # Arquivo local protegido: origem/assinatura do conteúdo foi preservada pelo worker.
        if metrics["source_end"]!=saved["source_end"]: raise ValueError("Arquivo de previsão divergente")
        snapshots.append(saved)
    if not snapshots: return
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
    actual["date"]=pd.to_datetime(actual.date)
    actual=actual.loc[actual.has_source_records & (actual.paid_orders>=5)]
    observed_field="paid_orders" if target=="paid_orders" else "amount_received_brl"
    compared=predicted.merge(actual[["date",observed_field]],on="date",how="inner").dropna()
    if len(compared)<7:
        st.info("Menos de sete dias observados elegíveis para comparar; envie mais dados completos. Não preenchemos dias ausentes com zero.")
        return
    cols=st.columns(3)
    format_value=(lambda value:"R$ "+f"{value:,.2f}".replace(",","X").replace(".",",").replace("X",".")) if target!="paid_orders" else (lambda value:f"{value:,.1f}".replace(",","X").replace(".",",").replace("X","."))
    cols[0].metric("Previsto nos dias comparáveis",format_value(compared.prediction.sum()))
    cols[1].metric("Realizado nos mesmos dias",format_value(compared[observed_field].sum()))
    cols[2].metric("Erro absoluto médio por dia",format_value((compared.prediction-compared[observed_field]).abs().mean()))
    chart=predicted.merge(actual[["date",observed_field]],on="date",how="left").set_index("date").rename(columns={"prediction":"Previsão original",observed_field:"Realizado"})
    st.line_chart(chart,color=["#1674d1","#159c94"])
    st.caption(f"Comparação em {len(compared)} dias elegíveis de {len(predicted)} dias de calendário da previsão. Datas ausentes ou com menos de cinco pedidos não são comparadas nem tratadas como venda zero. Totais acima são só dos mesmos dias comparáveis, não necessariamente do mês completo.")
