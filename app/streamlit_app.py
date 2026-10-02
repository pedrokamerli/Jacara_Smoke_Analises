"""Painel local de dados reais: agregados, origem explícita e ML reproduzível."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import duckdb
import pandas as pd
import streamlit as st

from jacare_analytics.pipeline import run_pipeline
from jacare_analytics.source_files import collect_local, collect_uploads
from jacare_analytics.dashboard_story import QUESTION_TITLES, INTERPRETATIONS, answer_summary
from jacare_analytics.business_calendar import freshness
from jacare_analytics.runtime_config import load_runtime_config, validate_public_manifest
from jacare_analytics.authentication import enforce_private_access, is_import_admin

ROOT = Path(__file__).resolve().parents[1]
MIN_GROUP = 5
st.set_page_config(page_title="Jacaré Analytics", page_icon="🐊", layout="wide")
try:
    RUNTIME = load_runtime_config(ROOT)
except ValueError:
    st.error("Configuração de execução inválida. O responsável deve revisar o modo público/privado e o diretório permitido.")
    st.stop()
enforce_private_access(RUNTIME.public_mode)
if not RUNTIME.public_mode:
    from jacare_analytics.private_dashboard import style_private, render_private
    style_private()
CURRENT = RUNTIME.current_manifest_path

PAGES = ["Visão geral", "15 perguntas e respostas", "Produtos", "Clientes", "Delivery", "Marketing", "Machine Learning", "Atualizar dados", "Metodologia"]
CHANNELS = {"ifood": "iFood", "menudino_app_site": "MenuDino — app/site", "desktop": "Desktop — origem PDV", "comanda_mobile": "Comanda mobile"}
LABELS = {"sale_date": "Data", "week_start": "Início da semana", "paid_orders": "Pedidos pagos", "amount_received_brl": "Valor recebido (R$)", "ticket": "Ticket recebido (R$)", "source_channel": "Canal", "product_name": "Produto", "product_category": "Categoria", "units_sold": "Unidades", "item_sales_brl": "Valor dos itens (R$)", "orders_containing_item": "Pedidos com item", "observed_days": "Dias com registro", "missing_days": "Dias sem registro", "metric_date": "Data", "spend_brl": "Gasto reportado (R$)", "impressions": "Impressões", "link_clicks": "Cliques no link", "cpc_brl": "CPC (R$)", "link_ctr": "CTR do link", "hour": "Hora", "received_brl": "Valor recebido (R$)", "order_status": "Status", "orders": "Registros", "items_value_brl": "Valor dos itens (R$)", "delivery_fee_brl": "Entrega (R$)"}
LABELS.update({
    "month_start":"Mês", "calendar_days":"Dias no calendário", "item_type":"Tipo de item",
    "first_date":"Primeira data", "last_date":"Última data", "average_ticket_brl":"Valor médio por pedido (R$)",
    "highest_value_rank":"Posição: maior valor", "lowest_value_rank":"Posição: menor valor",
    "highest_volume_rank":"Posição: maior volume", "lowest_volume_rank":"Posição: menor volume",
    "dimension":"Agrupamento", "value":"Dia / hora", "frequency_group":"Frequência de compras",
    "customers":"Clientes", "average_received_per_customer":"Valor médio acumulado por cliente (R$)",
    "identified_customers":"Clientes com código válido", "recurring_customers":"Clientes com duas ou mais compras",
    "recurrence_rate":"Recorrência", "identified_paid_orders":"Pedidos com código de cliente",
    "first_seen_customers":"Primeira aparição no histórico", "returning_customers":"Retorno de meses anteriores",
    "recency_group":"Tempo desde a última compra", "comparable_days":"Dias comparáveis",
    "same_count_days":"Dias com contagem igual", "items_difference_brl":"Diferença no valor dos itens (R$)",
    "covered_days":"Dias com registros", "first_order_date":"Primeira data", "last_order_date":"Última data",
    "sales_revenue_brl":"Receita de vendas reportada (R$)", "shop_revenue_brl":"Receita da loja reportada (R$)",
    "commission_expense_brl":"Comissões (R$)", "payment_channel_fee_brl":"Taxa de pagamento (R$)",
    "orders_with_both_timestamps":"Registros com conclusão e cancelamento preenchidos",
    "reported_dates":"Datas na fonte", "dates":"Datas comparadas", "reported_orders":"Pedidos na fonte",
    "pdv_paid_orders":"Pedidos pagos no sistema de vendas", "matching_dates":"Datas com contagem igual",
    "customer_paid_brl":"Valor pago pelo cliente (R$)", "metric_key":"Indicador",
    "observations":"Datas com valores", "first_value":"Primeiro valor reportado", "last_value":"Último valor reportado",
    "paired_dates":"Datas comparadas", "descriptive_correlation":"Associação entre gasto e vendas",
    "grupo":"Grupo de frequência", "clientes":"Clientes", "pedidos":"Pedidos",
    "valor_recebido":"Valor recebido (R$)", "valor_medio_por_cliente":"Valor médio acumulado por cliente (R$)",
    "tempo_sem_compra":"Tempo desde a última compra", "has_source_records":"Há registros na fonte?",
    "link_clicks_observed_rows":"Linhas de anúncio com cliques informados", "link_clicks_missing_rows":"Linhas de anúncio sem cliques informados",
    "delivery_type":"Tipo de entrega", "late_preparation_orders":"Registros de preparo atrasado",
    "average_prep_minutes":"Preparo médio reportado (minutos)", "average_acceptance_seconds":"Aceitação média reportada (segundos)", "average_finalization_seconds":"Finalização média reportada (segundos)",
})
SOCIAL_LABELS = {"reach":"Alcance", "views":"Visualizações", "content_interactions":"Interações", "profile_visits":"Visitas ao perfil", "link_clicks":"Cliques no link", "followers":"Seguidores (campo exportado)"}
PAGE_HELP = {
    "Visão geral":"Acompanhe o movimento realizado. No privado, os filtros no topo controlam cartões, gráficos e tabelas juntos.",
    "Produtos":"Compare quantidade, valor de vendas e presença nos pedidos. Mais vendido não significa mais lucrativo: não temos dados de custos.",
    "Clientes":"Entenda os hábitos de recompra por grupos. Nenhum nome, telefone, endereço ou código individual é mostrado.",
    "Delivery":"Veja MenuDino, iFood e 99Food e confira se os relatórios combinam com o sistema de vendas. Cada fonte pode cobrir datas diferentes.",
    "Marketing":"Acompanhe a atenção no Instagram e os resultados reportados dos anúncios. Cliques e visualizações não são compras comprovadas.",
}
METRIC_HELP = {
    "paid_orders":"Pedidos marcados como pagos no sistema de vendas. Não é quantidade de pessoas nem de produtos.",
    "amount_received_brl":"Soma do campo Total Recebido dos pedidos pagos. Não é lucro.",
    "ticket":"Valor recebido dividido pelo número de pedidos pagos.",
    "units_sold":"Quantidade de unidades registradas. Um pedido pode ter várias unidades.",
    "orders_containing_item":"Número de pedidos distintos em que este item apareceu.",
    "item_sales_brl":"Valor registrado para os itens; não inclui todos os ajustes do pedido e não representa margem.",
    "cpc_brl":"Custo por clique: gasto dos anúncios dividido pelos cliques no link.",
    "link_ctr":"Percentual de cliques por impressão: cliques no link ÷ impressões × 100.",
    "impressions":"Número de exibições do anúncio; uma pessoa pode vê-lo mais de uma vez.",
    "observed_days":"Datas que têm registros na fonte. Sem registro não significa necessariamente que a loja estava fechada.",
}


def money(value: float) -> str:
    return "R$ " + f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def table(frame: pd.DataFrame, *, currency_fields: tuple = ()) -> None:
    display = frame.copy()
    for field, mapping in {"source_channel":CHANNELS, "metric_key":SOCIAL_LABELS, "item_type":{"produto":"Produto avulso", "complemento":"Complemento", "item_de_combo":"Componente de combo"}, "dimension":{"hour":"Hora de abertura", "weekday":"Dia da semana (1=segunda; 7=domingo)"}}.items():
        if field in display:
            display[field] = display[field].map(lambda value: mapping.get(value, value))
    config = {}
    for field in display:
        label = LABELS.get(field, field)
        help_text = METRIC_HELP.get(field)
        if field in ("sale_date", "week_start", "month_start", "metric_date", "first_date", "last_date", "first_order_date", "last_order_date", "Data", "Treino até", "Teste de", "Teste até"):
            display[field] = pd.to_datetime(display[field], errors="coerce").dt.date
            config[label] = st.column_config.DateColumn(format="DD/MM/YYYY")
        elif field in ("link_ctr", "recurrence_rate"):
            display[field] = pd.to_numeric(display[field], errors="coerce") * 100
            config[label] = st.column_config.NumberColumn(format="%.2f%%", help=help_text)
        elif field in currency_fields or field.endswith("_brl") or field in ("ticket", "valor_recebido", "valor_medio_por_cliente", "average_received_per_customer"):
            config[label] = st.column_config.NumberColumn(format="R$ %.2f", help=help_text)
        elif field.startswith(("MAE:", "Erro médio:", "Estimativa", "Faixa exploratória:")):
            config[label] = st.column_config.NumberColumn(format="%.2f", help=help_text)
        elif field.startswith("WAPE:"):
            config[label] = st.column_config.NumberColumn(format="%.2f%%")
        elif help_text:
            config[label] = st.column_config.Column(help=help_text)
    st.dataframe(display.rename(columns=LABELS), column_config=config, hide_index=True, width="stretch")


def questions_page(manifest) -> None:
    st.write("Esta demonstração responde às mesmas perguntas com dados sintéticos independentes; não revela os resultados do cliente." if RUNTIME.public_mode else "Desenvolvi este projeto para transformar os arquivos reais da Jacaré Smoke House em respostas úteis para o negócio. Comecei pelas perguntas, conferi as fontes e preparei os dados antes de construir as análises e testar previsões.")
    st.info("Estas respostas usam o histórico completo da geração ativa, não um filtro de datas. Os relatórios de delivery e marketing mantêm os períodos próprios de cada fonte. Ao atualizar os dados, as respostas são recalculadas pelo mesmo processo.")
    st.caption("Como ler: primeiro a resposta em palavras; depois o que ela significa; por fim os cuidados e a tabela que permite conferir os números. Grupos pequenos são omitidos para reduzir a exposição de pessoas.")
    report_path = RUNTIME.resolve_artifact(manifest["analysis_report"])
    answers = json.loads(report_path.with_name("analysis_results.json").read_text(encoding="utf-8"))
    if [item["id"] for item in answers] != list(range(1, 16)):
        st.error("O relatório deve conter as 15 perguntas da geração ativa. Atualize os dados.")
        return
    selection = st.selectbox("Escolha uma pergunta ou veja todas", [0] + list(range(1,16)), format_func=lambda number: "Todas as 15 perguntas" if number == 0 else f"{number}. {QUESTION_TITLES[number-1]}")
    sections = {7:["Ranking por unidades vendidas", "Ranking por presença em pedidos"], 13:["Primeira aparição e retorno por mês", "Tempo sem compra até o fim do histórico"], 14:["MenuDino e iFood no sistema de vendas", "Conferência AppDelivery × MenuDino", "99Food — recorte próprio", "Conferência do arquivo adicional do iFood", "AppDelivery — evolução mensal por tipo e status"], 15:["Instagram — primeiro e último valor de cada série", "Meta Ads — totais sem repetir anúncios", "Associação entre gasto e vendas nas mesmas datas"]}
    for answer in answers:
        number = answer["id"]
        if selection not in (0, number):
            continue
        st.subheader(f"{number}. {QUESTION_TITLES[number-1]}")
        st.write(answer_summary(answer))
        st.write("**O que isso significa:** " + INTERPRETATIONS[number-1])
        st.caption("Cuidado na leitura: " + answer["limitation"])
        if number == 2 and answer["results"][0]:
            monthly = pd.DataFrame(answer["results"][0])
            chart = monthly.set_index(pd.to_datetime(monthly["month_start"]))
            chart.index.name = "Mês"
            st.line_chart(chart[["received_brl"]].rename(columns=LABELS), color="#20745B")
            st.caption("A linha acompanha o valor registrado por mês. Meses nas bordas da fonte ou do recorte podem estar incompletos; não representam vendas projetadas.")
        with st.expander(f"Conferir os dados da resposta {number}"):
            for index, rows in enumerate(answer["results"]):
                if number in sections:
                    st.write(sections[number][index])
                if rows:
                    table(pd.DataFrame(rows))
                    if number == 14 and index == 2:
                        st.caption("Tempos médios usam apenas durações positivas reportadas e exigem pelo menos cinco registros válidos. São campos da plataforma, não medições independentes. Conclusão e cancelamento preenchidos juntos não comprovam cancelamento.")
                else:
                    st.info("Sem grupos elegíveis nesta fonte.")
            st.caption(f"Consulta SQL reproduzível: {answer['sql']}. Posição 1 indica o extremo do ranking; empates compartilham a posição.")
    st.download_button("Baixar as 15 respostas", report_path.read_text(encoding="utf-8"), file_name="jacare_respostas_15_perguntas.md", mime="text/markdown")


def read_manifest() -> dict | None:
    if not CURRENT.exists():
        return None
    manifest = json.loads(CURRENT.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != 1 or not manifest.get("quality", {}).get("all_passed"):
        raise ValueError("A geração atual não possui uma auditoria válida.")
    if RUNTIME.public_mode:
        validate_public_manifest(manifest, RUNTIME)
    else:
        for key in ("warehouse", "forecast_metrics", "source_manifest", "quality_report", "analysis_report"):
            path = RUNTIME.resolve_artifact(manifest[key])
            if not path.is_relative_to(ROOT / "data/runs") or not path.exists():
                raise ValueError("Um artefato da geração atual está ausente ou fora do diretório de dados.")
    return manifest


@st.cache_data(show_spinner=False)
def query(sql: str, parameters: tuple, warehouse: str) -> pd.DataFrame:
    with duckdb.connect(warehouse, read_only=True) as connection:
        return connection.execute(sql, list(parameters)).df()


def import_page() -> None:
    if RUNTIME.queued_imports_enabled:
        from jacare_analytics.upload_ui import render_upload
        render_upload(RUNTIME, read_manifest())
        return
    if not RUNTIME.imports_enabled:
        st.info("Esta versão pública é somente leitura. A atualização é feita pelo responsável no ambiente privado.")
        return
    st.title("Atualizar dados")
    st.write("Envie os relatórios reais para refazer as análises, as 15 respostas e o experimento de previsão. O processo confere os dados antes de substituir os resultados atuais.")
    mode = st.radio("Origem", ["Pasta local", "Arquivos ou ZIPs"], horizontal=True)
    folder = st.text_input("Pasta com as fontes extraídas", value=str(ROOT)) if mode == "Pasta local" else None
    uploads = st.file_uploader("Selecione os pacotes de vendas e Instagram, ou seus arquivos oficiais", type=["zip", "xlsx", "csv"], accept_multiple_files=True) if mode == "Arquivos ou ZIPs" else []
    current = read_manifest() if CURRENT.exists() else None
    cutoff = st.date_input("Última data completa para análise", value=date.fromisoformat(current["cutoff"]) if current else date(2026, 8, 19), max_value=date.today(), format="DD/MM/YYYY")
    st.caption("Fontes necessárias: pedidos e itens consolidados, AppDelivery, 99Food e seis CSVs do Instagram. Meta Ads e o recorte adicional do iFood são opcionais. Arquivos enviados são lidos em memória; os originais permanecem intactos. A última data completa evita tratar um dia ainda em andamento como queda de vendas.")
    if st.button("Atualizar análises", type="primary"):
        try:
            with st.status("Processando fontes reais", expanded=True) as status:
                bundle = collect_local(Path(folder)) if folder else collect_uploads((upload.name, upload.getvalue()) for upload in uploads)
                manifest = run_pipeline(bundle, ROOT, cutoff, progress=st.write)
                status.update(label="Atualização validada", state="complete")
            st.cache_data.clear()
            st.session_state["import_success"] = f"Atualização concluída: {manifest['quality']['paid_orders']:,} pedidos pagos."
            st.rerun()
        except Exception:
            st.error("Atualização não concluída. Confira o formato, as fontes obrigatórias e se há versões conflitantes dos arquivos. Detalhes técnicos devem ser consultados somente no ambiente privado.")
            st.caption("O dashboard continua usando a última geração aprovada.")
    if CURRENT.exists():
        manifest = read_manifest()
        st.subheader("Fontes da geração ativa")
        table(pd.DataFrame([{"Fonte": key, "Arquivo": value["file"]} for key, value in manifest["sources"].items()]))


def overview(q, period, daily: pd.DataFrame) -> None:
    amount = float(daily["amount_received_brl"].sum())
    orders = int(daily["paid_orders"].sum())
    kpis = st.columns(4)
    kpis[0].metric("Valor recebido", money(amount), help=METRIC_HELP["amount_received_brl"])
    kpis[1].metric("Pedidos pagos", f"{orders:,}".replace(",", "."), help=METRIC_HELP["paid_orders"])
    kpis[2].metric("Valor médio por pedido", money(amount / orders) if orders else "—", help=METRIC_HELP["ticket"])
    kpis[3].metric("Datas sem registro", int((~daily["has_source_records"]).sum()), help="Datas sem linhas nos arquivos. Não inventamos vendas iguais a zero nessas datas.")
    st.caption("Valor recebido é o campo Total Recebido do PDV. Datas sem registro ficam ausentes nos gráficos. Horário atual informado: terça a domingo, 18h30–23h; exceções históricas ainda precisam ser conferidas.")
    st.caption("Legenda: PDV = sistema que registra os pedidos. Valor médio por pedido (ticket) = valor recebido ÷ pedidos pagos. Nos gráficos, a altura mostra valor ou quantidade e o eixo horizontal mostra as datas; lacunas não significam venda zero. Dias com menos de cinco pedidos não são exibidos individualmente.")
    visible = daily.copy()
    visible.loc[visible["paid_orders"] < MIN_GROUP, ["paid_orders", "amount_received_brl"]] = float("nan")
    chart = visible.set_index(pd.to_datetime(visible["sale_date"]))
    chart.index.name = "Data"
    left, right = st.columns(2)
    with left:
        st.subheader("Valor recebido por dia")
        st.line_chart(chart[["amount_received_brl"]].rename(columns=LABELS), color="#20745B")
    with right:
        st.subheader("Pedidos por dia")
        st.bar_chart(chart[["paid_orders"]].rename(columns=LABELS), color="#20745B")
    eligible = daily.loc[daily["paid_orders"] >= MIN_GROUP]
    if not eligible.empty:
        best = eligible.loc[eligible["amount_received_brl"].idxmax()]
        worst = eligible.loc[eligible["amount_received_brl"].idxmin()]
        high_orders = eligible.loc[eligible["paid_orders"].idxmax()]
        low_orders = eligible.loc[eligible["paid_orders"].idxmin()]
        cards = st.columns(4)
        for card, label, row, field in [(cards[0], "Maior valor diário", best, "amount_received_brl"), (cards[1], "Menor valor diário exibido", worst, "amount_received_brl"), (cards[2], "Maior volume diário", high_orders, "paid_orders"), (cards[3], "Menor volume diário exibido", low_orders, "paid_orders")]:
            card.metric(label, money(float(row[field])) if field == "amount_received_brl" else int(row[field]))
            card.caption(pd.to_datetime(row["sale_date"]).strftime("%d/%m/%Y"))
        st.caption("Rankings diários exibem dias com pelo menos cinco pedidos. Valores empatados mostram a primeira data.")
    weekly = q("select date_trunc('week',sale_date)::date as week_start, sum(paid_orders) as paid_orders, sum(amount_received_brl) as amount_received_brl, count(*) as calendar_days, count(*) filter(where has_source_records) as observed_days from analytics.fct_daily_sales where sale_date between cast(? as date) and cast(? as date) group by 1 order by 1", period)
    st.subheader("Semanas")
    complete = weekly.loc[(weekly["calendar_days"] == 7) & (weekly["paid_orders"] >= MIN_GROUP)]
    if not complete.empty:
        cols = st.columns(2)
        for col, label, index in [(cols[0], "Maior valor semanal registrado", complete["amount_received_brl"].idxmax()), (cols[1], "Menor valor semanal registrado", complete["amount_received_brl"].idxmin())]:
            row = complete.loc[index]
            col.metric(label, money(float(row["amount_received_brl"])))
            col.caption(f"Início: {pd.to_datetime(row['week_start']):%d/%m/%Y}; {int(row['observed_days'])}/7 dias com registro")
    table(weekly.loc[weekly["paid_orders"] >= MIN_GROUP])
    st.caption("Rankings semanais usam semanas de segunda a domingo inteiramente contidas no filtro. Dias sem registro tornam a cobertura operacional pendente.")
    monthly = q("select date_trunc('month',opened_at)::date as month_start, count(*) as paid_orders, sum(amount_received_brl) as amount_received_brl from analytics.stg_orders where order_status='paid' and cast(opened_at as date) between cast(? as date) and cast(? as date) group by 1 having count(*)>=5 order by 1", period)
    st.subheader("Evolução mensal")
    monthly_chart = monthly.set_index(pd.to_datetime(monthly["month_start"]))
    monthly_chart.index.name = "Mês"
    st.line_chart(monthly_chart[["amount_received_brl"]].rename(columns=LABELS), color="#20745B")
    st.caption("A linha mostra a evolução do valor recebido registrado mês a mês, não lucro ou projeções. Janeiro e agosto têm cobertura parcial no histórico completo; as bordas de qualquer filtro também podem estar incompletas.")
    channels = q("select source_channel,count(*) as paid_orders,sum(amount_received_brl) as amount_received_brl,avg(amount_received_brl) as ticket from analytics.stg_orders where order_status='paid' and cast(opened_at as date) between cast(? as date) and cast(? as date) group by 1 having count(*)>=5 order by amount_received_brl desc", period)
    channels["source_channel"] = channels["source_channel"].map(lambda value: CHANNELS.get(value, value))
    st.subheader("Canais registrados no PDV")
    table(channels)
    st.caption("Desktop e Comanda mobile são origens registradas no PDV; não presumimos que equivalem a plataformas ou modalidades de atendimento.")
    days = daily.loc[daily["paid_orders"] >= MIN_GROUP].copy()
    days["Dia da semana"] = pd.to_datetime(days["sale_date"]).dt.dayofweek.map(dict(enumerate(["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"])))
    hours = q("select hour,sum(paid_orders) as paid_orders,sum(received_brl) as received_brl from analytics.fct_sales_by_hour where sale_date between cast(? as date) and cast(? as date) group by 1 having sum(paid_orders)>=5 order by 1", period)
    left, right = st.columns(2)
    with left:
        st.subheader("Vendas por dia da semana")
        st.bar_chart(days.groupby("Dia da semana")["amount_received_brl"].sum().rename("Valor recebido (R$)"), color="#20745B")
    with right:
        st.subheader("Pedidos por hora de abertura")
        st.bar_chart(hours.rename(columns=LABELS).set_index("Hora")[["Pedidos pagos"]], color="#20745B")
    st.caption("Leitura dos gráficos: os dias da semana somam as vendas de todas as datas elegíveis no filtro, não são médias por dia. A hora é a abertura do pedido no sistema, não o tempo de preparo ou de entrega.")


def products(q, period) -> None:
    st.caption("Legenda: unidades = quantidade vendida; pedidos com item = quantas compras incluíram o item. Produto é vendido avulso; complemento é um adicional; item de combo é uma parte de um conjunto. Os rankings mostram somente grupos presentes em cinco ou mais pedidos.")
    frame = q("select i.product_name,i.product_category,i.item_type,sum(i.quantity) as units_sold,count(distinct i.order_key) as orders_containing_item,sum(i.line_total_brl) as item_sales_brl from analytics.stg_items i join analytics.stg_orders o using(order_key) where o.order_status='paid' and cast(o.opened_at as date) between cast(? as date) and cast(? as date) group by 1,2,3 having count(distinct i.order_key)>=5", period)
    kind = st.radio("Tipo de item", ["Todos", "Produtos", "Complementos", "Itens de combo"], horizontal=True)
    if kind != "Todos":
        frame = frame.loc[frame["item_type"].eq({"Produtos": "produto", "Complementos": "complemento", "Itens de combo": "item_de_combo"}[kind])]
    if frame.empty:
        st.info("Nenhum grupo com pelo menos cinco pedidos neste recorte.")
        return
    frame = frame.sort_values("units_sold", ascending=False)
    left, right = st.columns(2)
    with left:
        st.subheader("Mais unidades vendidas")
        st.bar_chart(frame.head(10).set_index("product_name")[["units_sold"]].rename(columns=LABELS), color="#20745B", horizontal=True)
    with right:
        st.subheader("Menor volume exibido")
        st.bar_chart(frame.tail(10).sort_values("units_sold").set_index("product_name")[["units_sold"]].rename(columns=LABELS), color="#BD8050", horizontal=True)
    st.subheader("Participação em pedidos e valor dos itens")
    table(frame)
    st.caption("Quantidade e valor dos itens não medem margem. Itens de combo são componentes registrados na fonte; não equivalem à contagem de combos completos.")


def customers(q, period, daily) -> None:
    result = q("with customers as(select customer_key,count(*) as orders from analytics.stg_orders where order_status='paid' and customer_key is not null and cast(opened_at as date) between cast(? as date) and cast(? as date) group by 1) select count(*) as identified,count(*) filter(where orders>=2) as recurring,coalesce(sum(orders),0) as covered_orders from customers", period).iloc[0]
    if int(result["identified"]) < 10:
        st.info("Este recorte não tem pelo menos dez clientes pseudonimizados para apresentar indicadores.")
        return
    cols = st.columns(3)
    cols[0].metric("Clientes com código protegido", int(result["identified"]), help="Um código local permite reconhecer compras repetidas sem mostrar dados pessoais. Não é o total de todos os clientes da hamburgueria.")
    cols[1].metric("Com duas ou mais compras", int(result["recurring"]))
    cols[2].metric("Recorrência no período", f"{result['recurring']/result['identified']:.1%}")
    st.caption(f"Cobertura: {int(result['covered_orders'])}/{int(daily['paid_orders'].sum())} pedidos pagos com chave de cliente válida. Os demais não são classificados como clientes únicos. Nenhum nome ou identificador é exibido.")
    st.caption("Legenda: recorrência = clientes com duas ou mais compras ÷ clientes com código válido. O valor médio por cliente soma suas compras no período, diferente do valor médio por pedido. As tabelas exibem grupos, nunca rankings individuais.")
    groups = q("with customers as(select customer_key,count(*) as orders,sum(amount_received_brl) as received from analytics.stg_orders where order_status='paid' and customer_key is not null and cast(opened_at as date) between cast(? as date) and cast(? as date) group by 1), bands as(select case when orders=1 then '1 pedido' when orders<=3 then '2–3 pedidos' when orders<=7 then '4–7 pedidos' else '8+ pedidos' end as faixa,orders,received from customers) select faixa as grupo,count(*) as clientes,sum(orders) as pedidos,sum(received) as valor_recebido,avg(received) as valor_medio_por_cliente from bands group by 1 having count(*)>=5 order by valor_medio_por_cliente desc", period)
    st.subheader("Grupos com maior valor médio por cliente")
    table(groups)
    monthly = q("with all_seen as(select customer_key,min(cast(opened_at as date)) as first_seen from analytics.stg_orders where order_status='paid' and customer_key is not null group by 1), monthly as(select distinct date_trunc('month',opened_at)::date as month_start,customer_key from analytics.stg_orders where order_status='paid' and customer_key is not null and cast(opened_at as date) between cast(? as date) and cast(? as date)) select month_start,count(*) filter(where date_trunc('month',first_seen)::date=month_start) as first_seen,count(*) filter(where date_trunc('month',first_seen)::date<month_start) as returning from monthly join all_seen using(customer_key) group by 1 having count(*)>=10 order by 1", period)
    st.subheader("Primeira observação e retorno por mês")
    st.bar_chart(monthly.rename(columns={"month_start":"Mês", "first_seen": "Primeira observação na fonte", "returning": "Retorno de mês anterior"}).set_index("Mês"))
    st.caption("Primeira observação no histórico disponível não prova que seja a primeira compra de toda a vida do cliente.")
    inactive = q("with clients as(select customer_key,max(cast(opened_at as date)) as last_seen from analytics.stg_orders where order_status='paid' and customer_key is not null and cast(opened_at as date)<=cast(? as date) group by 1) select case when date_diff('day',last_seen,cast(? as date))<=30 then 'Até 30 dias' when date_diff('day',last_seen,cast(? as date))<=60 then '31–60 dias' else 'Mais de 60 dias' end as tempo_sem_compra,count(*) as clientes from clients group by 1 having count(*)>=5", (period[1],period[1],period[1]))
    st.subheader("Tempo desde a última compra observada")
    table(inactive)
    st.caption(f"Referência: {period[1]}; cálculo sobre o histórico disponível até essa data.")


def delivery(q, period) -> None:
    st.caption("Legenda: conferir fontes significa comparar os relatórios para evitar contar uma mesma venda duas vezes. Valores de itens, entrega, total pago e receita da loja são medidas diferentes; não devem ser tratados como lucro. Uma plataforma com poucos dias de dados não pode ser classificada como pior pelo total bruto.")
    st.subheader("MenuDino e iFood no PDV")
    table(q("select source_channel,count(*) as paid_orders,sum(amount_received_brl) as amount_received_brl,avg(amount_received_brl) as ticket from analytics.stg_orders where order_status='paid' and source_channel in ('ifood','menudino_app_site') and cast(opened_at as date) between cast(? as date) and cast(? as date) group by 1 having count(*)>=5", period).replace({"source_channel": CHANNELS}))
    st.subheader("AppDelivery")
    table(q("select order_status,sum(orders) as orders,sum(items_value_brl) as items_value_brl,sum(delivery_fee_brl) as delivery_fee_brl from analytics.stg_appdelivery_daily where order_date between cast(? as date) and cast(? as date) group by 1 having sum(orders)>=5", period))
    with st.expander("Como o AppDelivery evoluiu por mês, tipo e status?"):
        table(q("select date_trunc('month',order_date)::date as month_start,delivery_type,order_status,sum(orders) as orders,sum(items_value_brl) as items_value_brl,sum(delivery_fee_brl) as delivery_fee_brl from analytics.stg_appdelivery_daily where order_date between cast(? as date) and cast(? as date) group by 1,2,3 having sum(orders)>=5 order by 1,2,3", period))
        st.caption("Cada linha combina um mês, um tipo de entrega e um status do arquivo. Grupos com menos de cinco registros são omitidos; meses nas bordas do filtro podem estar incompletos.")
    check = q("select count(*) as days,count(*) filter(where order_count_difference=0) as matching_days,sum(items_value_difference_brl) as delta from analytics.fct_appdelivery_reconciliation where order_date between cast(? as date) and cast(? as date) and appdelivery_delivered_orders>0 and pos_paid_orders>0", period).iloc[0]
    if int(check["days"]):
        st.info(f"Reconciliação AppDelivery × MenuDino: {int(check['matching_days'])}/{int(check['days'])} dias com a mesma contagem; diferença acumulada no valor dos itens: {money(float(check['delta']))}. As fontes não são somadas ao total do PDV.")
    st.subheader("99Food")
    food = q("select order_date,orders,sales_revenue_brl,shop_revenue_brl,commission_expense_brl,orders_with_both_timestamps from analytics.stg_food99_daily where order_date between cast(? as date) and cast(? as date) order by 1", period)
    if food.empty:
        st.info("Não há registros do 99Food no período selecionado.")
    else:
        cols = st.columns(3)
        cols[0].metric("Registros na fonte", int(food["orders"].sum()))
        cols[1].metric("Receita de vendas reportada", money(float(food["sales_revenue_brl"].sum())))
        cols[2].metric("Receita da loja reportada", money(float(food["shop_revenue_brl"].sum())))
        st.caption(f"{len(food)} dias cobertos neste recorte. Receita da loja é a métrica reportada pela plataforma; não equivale ao lucro do negócio.")
        st.write("Comissões reportadas:", money(float(food["commission_expense_brl"].sum())))
        if int(food["orders_with_both_timestamps"].sum()):
            st.caption("Há registros com conclusão e cancelamento preenchidos simultaneamente; não os classificamos automaticamente como cancelamentos.")
    st.subheader("Recorte adicional do iFood fornecido na aba iFood_App")
    extra = q("select order_status,sum(orders) as orders,sum(customer_paid_brl) as customer_paid_brl,min(order_date) as first_date,max(order_date) as last_date from analytics.stg_ifood_daily where order_date between cast(? as date) and cast(? as date) group by 1 having sum(orders)>=5", period)
    if extra.empty:
        st.info("Sem pedidos deste recorte adicional no filtro selecionado.")
    else:
        table(extra)
        reconciliation = q("select count(*) as dates, sum(reported_orders) as reported_orders,sum(pdv_paid_orders) as pdv_paid_orders,count(*) filter(where order_difference=0) as matching_dates from analytics.fct_ifood_reconciliation where order_date between cast(? as date) and cast(? as date)", period)
        table(reconciliation)
        st.caption("Este recorte tem período próprio e não foi adicionado ao total do PDV. Contagem igual não confirma identidade dos pedidos; a tabela recebida não inclui ID para reconciliar individualmente.")


def marketing(q, period) -> None:
    st.subheader("Instagram")
    labels = SOCIAL_LABELS
    metric = st.selectbox("Indicador", list(labels), format_func=labels.get, key="social_metric")
    explanations = {"reach":"Alcance se refere às contas alcançadas, conforme a definição da exportação; não é número de compras.", "views":"Visualizações são exibições do conteúdo; a mesma pessoa pode aparecer mais de uma vez.", "content_interactions":"Interações são ações no conteúdo reportadas pelo Instagram. Não significam pedidos.", "profile_visits":"Visitas ao perfil mostram interesse em abrir a página, não compras confirmadas.", "link_clicks":"Cliques no link indicam acesso ao destino do link. Um clique não garante um pedido.", "followers":"Seguidores é o nome do campo no arquivo. Ainda precisamos confirmar se ele mede novos seguidores ou outra variação; não o tratamos como o total da base."}
    st.write(explanations[metric])
    social = q("select metric_date,metric_value from analytics.fct_instagram_daily where metric_key=? and metric_date between cast(? as date) and cast(? as date) order by 1", (metric,*period))
    if social.empty:
        st.info("Sem valores desse indicador no recorte.")
    else:
        st.line_chart(social.rename(columns={"metric_date":"Data"}).set_index("Data")["metric_value"].rename(labels[metric]), color="#20745B")
        st.caption("Valores preservados como exportados. A série não é somada; a definição diária/acumulada precisa ser confirmada por indicador.")
    ads = q("select * from analytics.fct_marketing_daily where metric_date between cast(? as date) and cast(? as date) order by 1", period)
    st.subheader("Meta Ads — detalhamento diário de anúncios")
    if ads.empty:
        st.info("Sem dados do Meta Ads no período. Essa fonte é opcional na importação.")
        return
    ads.loc[ads["paid_orders"] < MIN_GROUP, ["paid_orders", "amount_received_brl"]] = float("nan")
    cols = st.columns(3)
    cols[0].metric("Gasto reportado", money(float(ads["spend_brl"].sum())))
    cols[1].metric("Impressões", int(ads["impressions"].sum()))
    missing_clicks = int(ads["link_clicks_missing_rows"].sum())
    cols[2].metric("Cliques informados (parcial)" if missing_clicks else "Cliques no link", int(ads["link_clicks"].sum()))
    if missing_clicks:
        st.warning(f"{missing_clicks} linhas de anúncios não informam cliques. O número acima soma apenas os valores conhecidos, sem tratar os ausentes como zero. CPC e CTR ficam indisponíveis nas datas com cobertura incompleta.")
    table(ads)
    st.caption("Legenda: impressões = exibições dos anúncios, não pessoas únicas; CPC = gasto ÷ cliques; CTR = cliques ÷ impressões, em percentual. Os valores de vendas ao lado dos anúncios são da mesma data, não vendas atribuídas aos anúncios.")
    st.caption("Cada gasto entra uma vez: linhas diárias no nível de anúncio da exportação mais recente. Totais de campanha/conjunto/anúncio e relatórios antigos não são somados. O alcance não foi somado, pois pode repetir pessoas.")
    paired = ads[["spend_brl", "amount_received_brl"]].dropna()
    if len(paired) >= 10 and paired.nunique().min() > 1:
        st.write(f"Correlação descritiva entre gasto e valor recebido nas {len(paired)} datas coincidentes: {paired.corr().iloc[0,1]:.2f}.")
    st.caption("Vendas e gasto na mesma data não demonstram que o anúncio causou as vendas. Não calculamos custo para conquistar um cliente, retorno causado pelos anúncios ou lucro com esses dados.")
    st.caption("Como ler a associação: perto de +1, as duas medidas costumam subir juntas; perto de −1, caminham em direções opostas; perto de zero, não aparece uma relação linear clara. Isso não mede retorno do investimento.")


def monthly_projection(metrics, target) -> None:
    """Projeção separada das vendas reais: ponte recursiva antes do mês de interesse."""
    projection = metrics["targets"][target].get("monthly_projection")
    if not projection:
        st.info("Reprocesse as fontes para calcular a projeção do próximo mês completo após o histórico.")
        return
    months = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"]
    start = date.fromisoformat(projection["start"])
    title = f"{months[start.month-1]} de {start.year}"
    st.subheader(f"Projeção experimental para {title}")
    st.warning(f"Não temos vendas realizadas desse mês nos arquivos. Esta é uma projeção calculada na origem {pd.Timestamp(projection['forecast_origin']):%d/%m/%Y}, não uma medição do mês nem uma previsão atualizada. O teste avaliou apenas 7 dias, não os {projection['horizon_from_origin_days']} dias usados aqui. Nenhum modelo está aprovado para uso operacional.")
    summary = projection["summary"]
    cols = st.columns(3)
    total = summary["predicted_total"]
    cols[0].metric(f"Total projetado — {months[start.month-1]}", money(total) if target == "total_received_brl" else f"{total:.2f}".replace(".", ",") + " pedidos")
    cols[1].metric("Dias de funcionamento planejados", f"{summary['predicted_open_days']}/{summary['predicted_calendar_days']}")
    cols[2].metric("Horizonte desde a origem", f"{projection['horizon_from_origin_days']} dias")
    st.caption(f"O total soma expectativas diárias, não vendas observadas. Antes de chegar ao mês, o modelo estima também {projection['bridge_days']} dias de ponte depois da última venda disponível, sem pular datas. Cada estimativa alimenta a próxima; erros podem se acumular. Não apresentamos um intervalo mensal de confiança sem validação.")
    st.caption("Pedidos e valor recebido foram projetados por modelos independentes: dividir esses totais não produz um ticket validado nem um demonstrativo financeiro coerente. O histórico até agosto também não cobre um ciclo anual completo para aprender sazonalidade de setembro.")
    rows = pd.DataFrame(projection["predictions"])
    chart = rows.set_index(pd.to_datetime(rows["date"]))[["prediction"]].rename(columns={"prediction":"Projeção diária"})
    chart.index.name = "Data projetada"
    st.line_chart(chart, color="#BD8050")
    st.caption("Linha laranja = projeção do modelo; não existe linha de realizado para este mês. Zeros nas segundas-feiras representam fechamento planejado. Pedidos fracionários expressam expectativa, não parte de uma compra registrada.")
    display = rows.rename(columns={"date":"Data", "prediction":"Projeção diária"})
    display["Situação"] = display["scheduled_open"].map({True:"Funcionamento previsto", False:"Fechamento planejado"})
    display = display.drop(columns=["scheduled_open", "prediction_origin"])
    with st.expander("Conferir os 30 dias projetados" if summary["predicted_calendar_days"] == 30 else "Conferir os dias projetados"):
        table(display, currency_fields=("Projeção diária",) if target == "total_received_brl" else ())
        st.download_button("Baixar a projeção mensal (CSV)", display.to_csv(index=False).encode("utf-8-sig"), file_name=f"jacare_projecao_{projection['month']}_{target}.csv", mime="text/csv")
    st.caption(projection["validation_policy"])


def machine_learning(manifest) -> None:
    metrics = json.loads(RUNTIME.resolve_artifact(manifest["forecast_metrics"]).read_text(encoding="utf-8"))
    if metrics.get("schema_version") != 4 or metrics.get("series_sha256") != manifest.get("series_sha256"):
        st.error("O experimento de ML não corresponde à série da geração ativa. Atualize os dados.")
        return
    st.write("Quantos pedidos serão pagos e quanto será recebido por dia? Comparei quatro modelos de aprendizado de máquina com duas regras simples. Eles procuram padrões nas vendas passadas para produzir estimativas, não certezas.")
    st.caption(f"Histórico de {pd.Timestamp(metrics['source_start']):%d/%m/%Y} a {pd.Timestamp(metrics['source_end']):%d/%m/%Y}: {metrics['observed_target_days']} dias com resultados conhecidos e {metrics['missing_target_days']} datas sem registros. Aqui usamos o histórico completo, sem o filtro das outras telas.")
    calendar = metrics["calendar"]
    current_freshness = freshness(date.fromisoformat(metrics["source_end"]), calendar)
    if RUNTIME.public_mode and metrics.get("public_display_policy"):
        st.caption(metrics["public_display_policy"]["policy"])
    st.info(f"Funcionamento informado: terça a domingo, {calendar['opens_at']}–{calendar['closes_at']} (horário de Bauru). Segunda-feira é fechamento planejado na estimativa, não venda zero adicionada ao histórico.")
    if not current_freshness["supports_current_week"]:
        st.warning(f"A fonte termina em {pd.Timestamp(metrics['source_end']):%d/%m/%Y}, há {current_freshness['days_since_source_end']} dias. As estimativas começam depois dessa data e NÃO representam previsão para a semana atual. Para isso, precisamos de vendas recentes.")
    with st.expander("Como aprendem os quatro modelos e como comparo os resultados?"):
        st.write("Random Forest combina árvores de decisão. Extra Trees combina árvores com mais aleatoriedade. Hist Gradient Boosting constrói árvores que corrigem os erros das anteriores. Ridge é uma regressão regularizada: uma combinação mais simples de sinais, com controle para evitar ajustes exagerados.")
        st.write("Todos recebem calendário, vendas defasadas e médias anteriores, sem nomes, telefones ou endereços. As referências simples repetem o mesmo dia da semana passada ou usam a média recente de sete dias.")
        st.write("Escolho o algoritmo ML nas seis primeiras semanas de teste. Congelo essa escolha antes das duas semanas finais, reservadas para avaliação. Em cada semana, o treino usa somente informações anteriores. Esse teste no passado é chamado backtest. Não escolho outro modelo olhando o resultado final.")
        st.caption("Datas sem registro continuam sem alvo. A mediana preenche somente entradas do modelo, aprendida no treino. O backtest valida previsões de sete dias; o segundo bloco da estimativa de 14 dias é exploratório e ainda não tem avaliação independente desse horizonte.")
    target = st.selectbox("O que prever", ["paid_orders", "total_received_brl"], key="ml_target", format_func=lambda key: {"paid_orders":"Pedidos pagos por dia", "total_received_brl":"Valor recebido por dia (R$)"}[key])
    result = metrics["targets"][target]
    selected_label = metrics["model_labels"][result["selected_model"]]
    format_error = (lambda value: f"{value:.2f}".replace(".", ",") + " pedidos") if target == "paid_orders" else money
    st.subheader(f"Modelo selecionado: {selected_label}")
    st.caption(f"Escolha encerrada em {pd.Timestamp(result['selection_end']):%d/%m/%Y}; teste final a partir de {pd.Timestamp(result['holdout_start']):%d/%m/%Y}. O melhor algoritmo ML não necessariamente vence as regras simples.")
    cols = st.columns(3)
    final = result["candidate_models"][result["selected_model"]]["holdout"]
    cols[0].metric("Erro médio diário — teste final", format_error(final["mae"]), help="MAE: distância média entre estimativa e realizado nas duas semanas que não participaram da escolha. Menor é melhor; não é um limite máximo de erro.")
    cols[1].metric("Erro final — semana anterior", format_error(result["candidate_models"]["seasonal_naive"]["holdout"]["mae"]))
    cols[2].metric("Dias comparáveis — teste final", result["holdout_comparable_days"], help="Amostra pequena: duas semanas de calendário, somente datas com resultado real e referências disponíveis.")
    st.write(f"No teste final, o modelo ficou, em média, {format_error(final['mae'])} distante do resultado real. Pode errar para cima ou para baixo.")
    monthly_projection(metrics, target)
    st.subheader("Comparação dos quatro modelos e das duas referências")
    model_names = {**metrics["model_labels"], "seasonal_naive":"Repetir a semana anterior", "moving_average_7d":"Média recente de 7 dias"}
    rows = []
    for name, scores in result["candidate_models"].items():
        rows.append({"Método":model_names[name], "Papel":"ML selecionado" if name == result["selected_model"] else "Referência simples" if name in ("seasonal_naive", "moving_average_7d") else "ML candidato", "MAE: seleção (6 semanas)":scores["selection"]["mae"], "MAE: teste final (2 semanas)":scores["holdout"]["mae"], "MAE: geral (diagnóstico)":scores["overall"]["mae"], "WAPE: teste final (%)":None if scores["holdout"]["wape"] is None else scores["holdout"]["wape"]*100})
    table(pd.DataFrame(rows))
    st.caption(f"MAE = erro absoluto médio, em pedidos ou reais por dia; menor é melhor. Seleção escolhe o algoritmo; teste final avalia a escolha. Geral inclui as semanas usadas para escolher, portanto não é evidência independente. Os seis métodos usam os mesmos {result['test_days']} dias comparáveis; {result['excluded_comparison_days']} datas foram excluídas por falta do realizado ou da referência.")
    st.caption("WAPE = soma dos erros absolutos ÷ soma do realizado, em percentual. Não é taxa de acerto nem 'precisão'. É possível ter WAPE maior que 100%.")
    baseline_rows = []
    for key, name in [("seasonal_naive", "Repetir a semana anterior"), ("moving_average_7d", "Média recente de 7 dias")]:
        gain = result["mae_improvement_by_baseline"][key]
        baseline_rows.append({"Regra de comparação":name, "Redução geral de MAE":f"{gain:.1%}".replace(".", ",") if gain is not None else "Não calculável", "Semanas vencidas":f"{result['fold_wins'][key]}/{result['folds']}", "Critério geral":"Atingido" if result["baseline_gates_passed"][key] else "Não atingido", "Menor erro no teste final?":"Sim" if result["holdout_gates_passed"][key] else "Não"})
    table(pd.DataFrame(baseline_rows))
    st.caption("Redução positiva = menos erro; negativa = mais erro. O critério exige melhorar contra as duas referências e também vencer no teste final, não apenas na comparação mais favorável.")
    st.subheader("O que aconteceu × o que teríamos estimado")
    predictions = pd.DataFrame(result["backtest_predictions"]).set_index("date")
    predictions.index = pd.to_datetime(predictions.index)
    predictions.index.name = "Data"
    graph_models = st.multiselect("Métodos no gráfico", list(model_names), default=[result["selected_model"], "seasonal_naive"], format_func=model_names.get)
    st.line_chart(predictions[["actual", *graph_models]].rename(columns={"actual":"Realizado", **model_names}))
    st.caption("Realizado é o registro da fonte; as demais linhas são estimativas. Linhas mais próximas do realizado indicam menos erro. Lacunas não significam zero. As duas últimas semanas são o teste final reservado.")
    st.subheader("Conferência dos testes, período por período")
    st.write("Cada linha abaixo é uma semana escondida do modelo. 'Treino até' mostra a última data disponível para aprender; o teste começa depois dela. A tabela ajuda a ver se a melhora é consistente, em vez de depender de uma única semana.")
    folds = pd.DataFrame([{ "Período": row["fold"], "Etapa":"Seleção" if row["stage"] == "selection" else "Teste final", "Treino até": row["train_end"], "Teste de": row["test_start"], "Teste até": row["test_end"], "Dias comparáveis": row["compared_days"], "Erro médio: modelo": row["ml"]["mae"], "Erro médio: semana anterior": row["seasonal_naive"]["mae"], "Erro médio: média recente": row["moving_average_7d"]["mae"]} for row in result["fold_details"]])
    table(folds)
    st.caption("Erros desta tabela estão em pedidos por dia ou reais por dia, conforme a opção escolhida. Menor erro é melhor.")
    st.subheader("Estimativa experimental após o fim do histórico")
    horizon = st.radio("Horizonte da estimativa", [7, 14], key="ml_horizon", format_func=lambda value:f"{value} dias", horizontal=True)
    forecast = pd.DataFrame(result["experimental_forecast"][:horizon])
    forecast["Situação"] = forecast["scheduled_open"].map({True:"Funcionamento previsto", False:"Fechamento planejado"})
    forecast = forecast.drop(columns=["scheduled_open", "prediction_origin"]).rename(columns={"date":"Data", "prediction":"Estimativa do modelo", "residual_band_low":"Faixa exploratória: de", "residual_band_high":"Faixa exploratória: até"})
    st.write(f"Período estimado: {pd.Timestamp(forecast.iloc[0]['Data']):%d/%m/%Y} a {pd.Timestamp(forecast.iloc[-1]['Data']):%d/%m/%Y}. São resultados calculados, nunca adicionados às vendas reais.")
    forecast_chart = forecast.set_index(pd.to_datetime(forecast["Data"]))[["Estimativa do modelo", "Faixa exploratória: de", "Faixa exploratória: até"]]
    forecast_chart.index.name = "Data"
    st.line_chart(forecast_chart)
    table(forecast, currency_fields=("Estimativa do modelo", "Faixa exploratória: de", "Faixa exploratória: até") if target == "total_received_brl" else ())
    st.caption(f"Faixa exploratória: percentis 10 e 90 dos resíduos de apenas {result['holdout_comparable_days']} dias do teste final. Não é intervalo de confiança calibrado nem garantia de cobertura. Pedidos fracionários representam expectativa média. Segunda-feira aparece com zero pela regra de fechamento, não por observação de venda.")
    if horizon == 14:
        st.warning("O teste mede desempenho em sete dias. A segunda semana usa estimativas anteriores como entrada; erros podem se acumular. Ainda não validamos a qualidade específica do horizonte de 14 dias.")
    st.download_button("Baixar estimativas agregadas (CSV)", forecast.to_csv(index=False).encode("utf-8-sig"), file_name=f"jacare_estimativas_{target}_{horizon}d.csv", mime="text/csv")
    st.subheader("Já podemos usar para decidir compras ou equipe?")
    st.warning("Ainda não como ferramenta operacional. Precisamos de histórico atualizado e conferir as exceções históricas ao horário informado. Mostrar uma previsão não significa que ela esteja aprovada para compras ou escala de equipe.")
    st.write("O critério estatístico foi atingido neste indicador." if result["statistical_gate_passed"] else "O critério estatístico ainda não foi atingido neste indicador.")
    st.caption(metrics["promotion_gate"])
    review = metrics.get("calendar_review", {})
    if review:
        st.caption(f"Conferência do calendário: {review['paid_orders_on_monday']} pedidos pagos registrados em segundas-feiras e {review['paid_orders_outside_reference_hours']} abertos fora de {calendar['opens_at']}–{calendar['closes_at']}. Os registros foram preservados. A abertura no sistema pode anteceder o atendimento; esses números não provam erro na fonte.")
    with st.expander("Detalhes técnicos e sinais usados pelo modelo"):
        st.write(metrics["feature_policy"])
        names = {"weekday":"Dia da semana", "month":"Mês", "day":"Dia do mês", "dayofweek":"Dia da semana", "day_of_week":"Dia da semana", "day_of_month":"Dia do mês", "observed_days_7":"Dias conhecidos na última semana", "observed_days_28":"Dias conhecidos nas últimas 4 semanas", "mean_7":"Média dos últimos 7 dias", "mean_28":"Média dos últimos 28 dias", "rolling_mean_7":"Média dos últimos 7 dias", "rolling_mean_28":"Média dos últimos 28 dias"}
        for lag in (1,7,14,28):
            names[f"lag_{lag}"] = f"Venda de {lag} dia(s) antes"
        if result["feature_importance"]:
            importance = pd.Series(result["feature_importance"]).sort_values().tail(12)
            importance.index = [names.get(key, key.replace("missingindicator_", "Ausência de ").replace("_", " ")) for key in importance.index]
            st.bar_chart(importance.rename("Peso relativo no modelo"), horizontal=True)
            st.caption("No Ridge, são magnitudes normalizadas dos coeficientes padronizados; nas árvores, importância interna. Não medem efeito causal nem devem ser comparadas entre algoritmos.")
        else:
            st.info("Este algoritmo não fornece importância interna equivalente às árvores. Não inventamos pesos para completar o gráfico.")
        st.caption("Modelos ajustados ficam somente no ambiente privado. A versão pública não recebe arquivos de modelo, chaves ou pedidos individuais.")


def methodology(manifest) -> None:
    if RUNTIME.public_mode:
        st.info("As etapas abaixo descrevem o projeto. Nesta demo, a preparação parte do gerador sintético; a auditoria compara suas tabelas geradas, não planilhas reais. Os resultados desta tela não validam o modelo do cliente.")
    st.write("Meu objetivo é responder perguntas de uma hamburgueria real com um processo que outra pessoa consiga conferir e repetir. Por isso segui CRISP-DM, uma metodologia que organiza o trabalho em seis etapas — do problema do negócio à entrega e avaliação.")
    phases = [("1. Entendimento do negócio", "15 perguntas e definições de vendas, produtos, recorrência e marketing."), ("2. Entendimento dos dados", "Inventário de fontes, períodos, chaves, duplicidades e sobreposição."), ("3. Preparação", "Python lê os arquivos reais, minimiza campos pessoais, pseudonimiza chaves locais e gera Parquet."), ("4. Modelagem", "SQL/dbt constrói marts em DuckDB; scikit-learn compara quatro algoritmos ML com duas referências temporais."), ("5. Avaliação", "dbt build e reconciliação dos totais com a origem; escolha em seis semanas e avaliação nas duas semanas finais, nas mesmas datas observadas."), ("6. Implantação", "Dashboard e CLI privados usam a mesma geração validada. A versão pública lê somente um pacote agregado aprovado, sem arquivos originais ou importação.")]
    for title, text in phases:
        st.subheader(title)
        st.write(text)
    with st.expander("Para que serve cada tecnologia?", expanded=True):
        st.write("Python lê e prepara os arquivos. Parquet guarda os dados tratados em um formato eficiente. DuckDB consulta os dados localmente com SQL, sem precisar de PostgreSQL. dbt organiza as transformações SQL e seus testes. scikit-learn treina e avalia o modelo de previsão. Streamlit apresenta as análises e recebe novas importações.")
        st.write("Escolhi ferramentas proporcionais ao volume disponível. O projeto mostra engenharia, análise e Machine Learning, sem afirmar que um histórico pequeno exige infraestrutura de big data.")
    st.write("Na proteção dos dados, retirei campos pessoais dos dados analíticos e uso códigos protegidos apenas para contar retornos. No painel, exibo grupos e oculto recortes pequenos. Isso reduz exposição, mas não substitui autorização para uso e publicação dos dados do negócio.")
    st.subheader("Auditoria da geração")
    st.write(f"{manifest['dbt_models_built']} modelos SQL/dbt construídos; {manifest['dbt_tests_passed']} testes de qualidade aprovados.")
    check_names = {"paid_order_count_matches_preparation":"Contagem de pedidos confere com os dados tratados", "received_matches_preparation":"Valor recebido confere com os dados tratados", "paid_order_count_matches_raw":"Contagem de pedidos confere com o arquivo original", "received_matches_raw":"Valor recebido confere com o arquivo original", "items_have_orders":"Todos os itens têm um pedido correspondente", "orders_follow_privacy_allowlist":"Pedidos contêm apenas os campos permitidos", "items_follow_privacy_allowlist":"Itens contêm apenas os campos permitidos", "missing_calendar_days_match_source":"Datas sem registros conferem com a origem", "meta_ads_spend_matches_report_total":"Gasto de anúncios confere com o total do relatório"}
    table(pd.DataFrame([{"Verificação": check_names.get(key,key),"Resultado":"Concluída" if passed else "Falhou"} for key,passed in manifest["quality"]["checks"].items()]))
    st.caption("Horário atual confirmado: terça a domingo, 18h30–23h. Pendências: exceções históricas e datas sem registro, definições das métricas sociais e sobreposição AppDelivery × MenuDino. Uso operacional do modelo depende de histórico atualizado e avaliação adicional.")
    if "analysis_report" in manifest:
        report_path = RUNTIME.resolve_artifact(manifest["analysis_report"])
        st.download_button("Baixar as respostas às 15 perguntas", report_path.read_text(encoding="utf-8"), file_name="jacare_respostas_15_perguntas.md", mime="text/markdown")


def public_page(page, manifest) -> None:
    """A versão pública nunca consulta pedidos/chaves individuais ou aceita filtros livres."""
    if page == "15 perguntas e respostas":
        questions_page(manifest)
        return
    if page == "Machine Learning":
        machine_learning(manifest)
        return
    if page == "Metodologia":
        methodology(manifest)
        return
    answers = json.loads(RUNTIME.resolve_artifact(manifest["analysis_results"]).read_text(encoding="utf-8"))
    st.info("Demo somente leitura: recorte fixo sintético, sem acesso aos arquivos ou resultados reais. Produtos, vendas, canais e marketing nesta tela são exemplos fictícios.")
    sections = {"Visão geral":[1,2,3,4,5,6], "Produtos":[7,8,9,10], "Clientes":[11,12,13], "Delivery":[14], "Marketing":[15]}
    if page == "Visão geral":
        summary = manifest["quality"]
        columns = st.columns(3)
        columns[0].metric("Pedidos pagos", summary["paid_orders"])
        columns[1].metric("Valor recebido", money(summary["received_brl"]))
        columns[2].metric("Datas sem registros", summary["missing_days"])
        monthly = pd.DataFrame(answers[1]["results"][0])
        if not monthly.empty:
            chart = monthly.set_index(pd.to_datetime(monthly["month_start"]))
            chart.index.name = "Mês"
            st.line_chart(chart[["received_brl"]].rename(columns=LABELS), color="#20745B")
            st.caption("Valor recebido não é lucro. Janeiro e agosto podem ter cobertura parcial; a linha mostra os valores registrados, não projeções de meses completos.")
    for number in sections[page]:
        answer = answers[number-1]
        st.subheader(f"{number}. {QUESTION_TITLES[number-1]}")
        st.write(answer_summary(answer))
        st.caption(answer["limitation"])
        for rows in answer["results"]:
            if rows:
                table(pd.DataFrame(rows))
            else:
                st.info("Sem grupos elegíveis para publicação neste resultado.")


def main() -> None:
    st.sidebar.title("Jacaré Analytics")
    st.sidebar.caption("Bauru / SP")
    can_import=RUNTIME.imports_enabled or (RUNTIME.queued_imports_enabled and is_import_admin(RUNTIME.public_mode))
    page = st.sidebar.radio("Análises", PAGES if can_import else [item for item in PAGES if item != "Atualizar dados"])
    st.sidebar.caption("DEMO · dados fictícios" if RUNTIME.public_mode else "REAL · confidencial · acesso restrito")
    if RUNTIME.public_mode:
        st.info("DEMONSTRAÇÃO: todos os valores, clientes, produtos e previsões são sintéticos. Não representam o negócio real. O ML foi treinado separadamente com a base fictícia.")
    else:
        st.caption("ÁREA PRIVADA · dados reais e confidenciais · não compartilhar capturas ou downloads com terceiros.")
    if "import_success" in st.session_state:
        st.success(st.session_state.pop("import_success"))
    if page == "Atualizar dados":
        import_page()
        return
    try:
        manifest = read_manifest()
    except (OSError, ValueError, KeyError):
        st.error("Não foi possível abrir uma geração aprovada. Confira os artefatos e as verificações de qualidade; na versão pública, é necessário um pacote agregado autorizado.")
        return
    if manifest is None:
        st.info("Nenhum pacote agregado autorizado disponível para publicação." if RUNTIME.public_mode else "Login autorizado. Os dados reais ainda não foram disponibilizados nesta instância; aguardamos a homologação do acesso." if RUNTIME.read_only else "Selecione Atualizar dados para processar as fontes reais antes de abrir as análises.")
        return
    st.title("Machine Learning — previsão de demanda" if page == "Machine Learning" else page)
    kind = "demonstração sintética" if RUNTIME.public_mode else "somente arquivos reais"
    st.caption(f"Histórico principal de vendas • {pd.Timestamp(manifest['source_start']):%d/%m/%Y} a {pd.Timestamp(manifest['source_end']):%d/%m/%Y} • {kind}")
    st.sidebar.caption("Stack: Python · Parquet · DuckDB · SQL/dbt · Streamlit · scikit-learn")
    st.sidebar.caption("Passe o cursor nos ícones de ajuda dos indicadores e nos títulos das colunas para ler as definições.")
    if page in PAGE_HELP:
        st.write(PAGE_HELP[page])
    if RUNTIME.public_mode:
        public_page(page, manifest)
        return
    if page == "15 perguntas e respostas":
        st.caption("ESCOPO: histórico completo da geração. Esta página não usa filtros de vendas; cada resposta informa seus limites.")
        questions_page(manifest)
        return
    if page == "Machine Learning":
        st.caption("ESCOPO: experimento salvo da geração completa. Filtros de vendas não retreinam nem alteram a origem do modelo.")
        machine_learning(manifest)
        from jacare_analytics.forecast_archive import render_comparison
        render_comparison(RUNTIME,manifest)
        return
    if page == "Metodologia":
        methodology(manifest)
        return
    render_private(page, manifest, ROOT, table, lambda sql,params=(): query(sql,tuple(params),str(ROOT/manifest["warehouse"])), delivery, marketing)


main()
