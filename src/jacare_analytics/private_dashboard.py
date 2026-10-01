"""Dashboard privado: um contrato de filtros para indicadores, gráficos e tabelas."""
from __future__ import annotations
from dataclasses import dataclass, replace
from datetime import date, timedelta
import altair as alt
import duckdb
import pandas as pd
import streamlit as st

BLUE, TEAL, AMBER = "#1674d1", "#159c94", "#d58b32"
CHANNELS = {"ifood":"iFood", "menudino_app_site":"MenuDino / app e site", "desktop":"Desktop / origem PDV", "comanda_mobile":"Comanda mobile"}
DAYS = ("Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo")

@dataclass(frozen=True)
class SalesFilter:
    start: date
    end: date
    channels: tuple[str,...] | None = None
    order_types: tuple[str,...] | None = None
    weekdays: tuple[int,...] = tuple(range(7))

    def predicate(self):
        if self.start > self.end or any(x not in range(7) for x in self.weekdays):
            raise ValueError("Filtro inválido")
        clauses, params = ["order_status='paid'", "cast(opened_at as date) between ? and ?"], [self.start,self.end]
        for field, values in (("source_channel",self.channels),("order_type",self.order_types),("(isodow(opened_at)-1)",self.weekdays)):
            if values is None: continue
            if not values: clauses.append("false")
            else:
                clauses.append(field+" in ("+",".join("?" for _ in values)+")")
                params.extend(values)
        return " and ".join(clauses), params

def execute_sales(warehouse, filters, sql, parameters=()):
    predicate, params = filters.predicate()
    with duckdb.connect(str(warehouse),read_only=True) as db:
        return db.execute("with selected_orders as (select * from analytics.stg_orders where "+predicate+") "+sql,params+list(parameters)).df()

@st.cache_data(show_spinner=False)
def sales_query(warehouse, run_id, filters, sql, parameters=()):
    # Geração e todas as dimensões entram na chave; não criar views globais por sessão.
    return execute_sales(warehouse,filters,sql,parameters)

def money(value):
    return "R$ "+f"{float(value):,.2f}".replace(",","X").replace(".",",").replace("X",".")

def style_private():
    st.markdown("""<style>
    .stApp {background:#eef3f8;color:#18364d;}
    .stMainBlockContainer {max-width:1480px;padding-top:1.5rem;padding-bottom:2rem;}
    .stMain [data-testid="stVerticalBlock"] {gap:.65rem;}
    h1 {font-size:1.8rem!important;} h2,h3 {font-size:1.15rem!important;}
    [data-testid="stSidebar"] {background:#082c4d;min-width:235px;max-width:265px;}
    [data-testid="stSidebar"] p,[data-testid="stSidebar"] h1,[data-testid="stSidebar"] label,
    [data-testid="stSidebar"] [data-testid="stCaptionContainer"] {color:#e3eef8!important;}
    [data-testid="stSidebar"] button {color:#143651!important;}
    [data-testid="stMetric"] {background:white;border:1px solid #dfe8f1;border-radius:12px;
      border-top:3px solid #1674d1;padding:12px 14px;min-height:96px;}
    [data-testid="stMetricValue"] {font-size:1.65rem!important;}
    .st-key-sales_toolbar,[class*="st-key-panel_"] {border-radius:12px;background:white;}
    [data-testid="stAlert"] {border-radius:10px;}
    </style>""",unsafe_allow_html=True)

def plot(frame,x,y,*,kind="line",horizontal=False,color=BLUE,x_title=None,y_title=None,height=235,order=None):
    if frame.empty or not frame[y].notna().any():
        st.info("Sem valores elegíveis neste recorte. Amplie o período ou os filtros.")
        return
    fields=frame[[x,y]].copy()
    temporal=pd.api.types.is_datetime64_any_dtype(fields[x])
    tooltip=[alt.Tooltip(x+(":T" if temporal else ":N"),title=x_title or x,format="%d/%m/%Y" if temporal else alt.Undefined),alt.Tooltip(y+":Q",title=y_title or y,format=",.2f")]
    chart=alt.Chart(fields)
    if horizontal:
        chart=chart.mark_bar(color=color,cornerRadiusEnd=4).encode(y=alt.Y(x+":N",title=None,sort=order or "-x",axis=alt.Axis(labelLimit=220)),x=alt.X(y+":Q",title=y_title or y),tooltip=tooltip)
    else:
        chart=(chart.mark_line(point=alt.OverlayMarkDef(filled=True,size=45),color=color,strokeWidth=2.5) if kind=="line" else chart.mark_bar(color=color,cornerRadiusTopLeft=3,cornerRadiusTopRight=3)).encode(
            x=alt.X(x+(":T" if temporal else ":O"),title=x_title or x,sort=order,axis=alt.Axis(labelAngle=0,format="%d/%m" if temporal else alt.Undefined)),y=alt.Y(y+":Q",title=y_title or y,scale=alt.Scale(zero=True)),tooltip=tooltip)
    chart=chart.configure(locale={"number":{"decimal":",","thousands":".","grouping":[3],"currency":["R$ ",""]}})
    st.altair_chart(chart.properties(height=height).configure_view(stroke=None).configure_axis(labelColor="#4c647c",titleColor="#4c647c",gridColor="#edf2f7",labelFontSize=11,titleFontSize=11),width="stretch")

def reset_filters():
    for key in list(st.session_state):
        if key.startswith("sales_") or key.startswith("product_"): del st.session_state[key]

def filter_bar(manifest,warehouse,page):
    low,high=date.fromisoformat(manifest["source_start"]),date.fromisoformat(manifest["source_end"])
    with st.container(border=True,key="sales_toolbar"):
        cols=st.columns([2,3,1])
        preset=cols[0].selectbox("Período de análise",["Histórico completo","Mês específico","Últimos 30 dias da base","Personalizado"],key="sales_preset")
        if preset=="Mês específico":
            months=pd.period_range(low,high,freq="M").strftime("%Y-%m").tolist()
            month=cols[1].selectbox("Mês",months,index=len(months)-1,key="sales_month")
            first=date.fromisoformat(month+"-01")
            start,end=max(low,first),min(high,(pd.Timestamp(first)+pd.offsets.MonthEnd()).date())
        elif preset=="Personalizado":
            interval=cols[1].date_input("Data inicial e final",value=(low,high),min_value=low,max_value=high,format="DD/MM/YYYY",key="sales_dates")
            if len(interval)!=2:
                st.info("Escolha as duas datas para aplicar o filtro.")
                return None
            start,end=interval
        else:
            start,end=(max(low,high-timedelta(days=29)),high) if preset=="Últimos 30 dias da base" else (low,high)
            cols[1].markdown(f"**{start:%d/%m/%Y} a {end:%d/%m/%Y}**")
            cols[1].caption("Última data da base, não a data de hoje.")
        cols[2].button("Limpar filtros",on_click=reset_filters,width="stretch")
        channels,modes,weekdays=None,None,tuple(range(7))
        if page in {"Visão geral","Produtos","Clientes"}:
            dimensions=sales_query(warehouse,manifest["run_id"],SalesFilter(low,high),"select distinct source_channel,order_type from selected_orders")
            all_channels=sorted(dimensions.source_channel.dropna().unique().tolist())
            all_modes=sorted(dimensions.order_type.dropna().unique().tolist())
            cols=st.columns(3)
            channels=tuple(cols[0].multiselect("Canais do PDV",all_channels,default=all_channels,format_func=lambda x:CHANNELS.get(x,x),key="sales_channels"))
            modes=tuple(cols[1].multiselect("Tipo de pedido registrado",all_modes,default=all_modes,format_func=lambda x:{"balcao":"Balcão","mesa_comanda":"Mesa / comanda","delivery":"Delivery"}.get(x,x),key="sales_modes"))
            weekdays=tuple(cols[2].multiselect("Dias da semana",list(range(7)),default=list(range(7)),format_func=lambda x:DAYS[x],key="sales_weekdays"))
            if all_channels and set(channels)==set(all_channels): channels=None
            if all_modes and set(modes)==set(all_modes): modes=None
            st.caption(f"Canais: {'todos' if channels is None else len(channels)} · Tipos: {'todos' if modes is None else len(modes)} · Dias da semana: {len(weekdays)}/7")
            st.caption("Cartões, gráficos e tabelas usam os mesmos filtros. Seleção vazia = nenhum registro; Limpar filtros restaura tudo.")
        else:
            st.caption("Filtro temporal aplicado separadamente a cada fonte. Canal do PDV não é filtro de Instagram ou relatórios externos sem vínculo comprovado.")
        st.caption(f"RECORTE ATIVO · {start:%d/%m/%Y} a {end:%d/%m/%Y} · {(end-start).days+1} dias de calendário")
    return SalesFilter(start,end,channels,modes,weekdays)

SUMMARY="select count(*) as orders,coalesce(sum(amount_received_brl),0) as amount,count(distinct cast(opened_at as date)) as active_days from selected_orders"
PRODUCTS="""select i.product_name,i.product_category,i.item_type,sum(i.quantity) as units,
 count(distinct i.order_key) as orders,sum(i.line_total_brl) as amount
 from analytics.stg_items i join selected_orders o using(order_key)
 group by 1,2,3 having count(distinct i.order_key)>=5"""

def item_labels(frame):
    frame=frame.copy()
    frame["item_label"]=frame.product_name
    duplicate=frame.product_name.duplicated(keep=False)
    kind=frame.item_type.map({"produto":"avulso","complemento":"adicional","item_de_combo":"componente"}).fillna(frame.item_type)
    frame.loc[duplicate,"item_label"]=frame.loc[duplicate,"product_name"]+" / "+kind.loc[duplicate]+" / "+frame.loc[duplicate,"product_category"].fillna("sem categoria")
    return frame

def overview(sq,filters,manifest,table):
    summary=sq(SUMMARY).iloc[0]
    previous=None
    length=(filters.end-filters.start).days+1
    previous_start=filters.start-timedelta(days=length)
    if previous_start>=date.fromisoformat(manifest["source_start"]):
        previous=sq(SUMMARY,custom=replace(filters,start=previous_start,end=filters.start-timedelta(days=1))).iloc[0]
    count,amount=int(summary.orders),float(summary.amount)
    values=[amount,count,amount/count,int(summary.active_days)]
    old=None
    if previous is not None and int(previous.orders)>=5:
        old=[float(previous.amount),int(previous.orders),float(previous.amount)/int(previous.orders),int(previous.active_days)]
    for i,(col,label,help_text) in enumerate(zip(st.columns(4),["Valor recebido","Pedidos pagos","Ticket médio","Dias com pedidos"],["Recebido dos pedidos pagos, não lucro.","Pedidos, não clientes ou unidades.","Valor recebido dividido por pedidos pagos.","Dias com pedidos que atendem aos filtros; não comprova todos os dias abertos."])):
        delta=None if not old or not old[i] else f"{values[i]/old[i]-1:+.1%}".replace(".",",")
        col.metric(label,money(values[i]) if i in (0,2) else f"{values[i]:,}".replace(",","."),delta=delta,help=help_text)
    st.caption("Variação versus intervalo anterior de igual duração, com os mesmos filtros." if old else "Sem intervalo anterior elegível. Valores realizados; sem custos, não calculamos lucro.")
    daily=sq("select cast(opened_at as date) as day,count(*) as orders,sum(amount_received_brl) as amount from selected_orders group by 1 order by 1")
    calendar=pd.DataFrame({"day":pd.date_range(filters.start,filters.end)})
    calendar=calendar.loc[calendar.day.dt.weekday.isin(filters.weekdays)]
    daily["day"]=pd.to_datetime(daily["day"])
    daily=calendar.merge(daily,on="day",how="left")
    daily.loc[daily.orders<5,["orders","amount"]]=float("nan")
    monthly=sq("select date_trunc('month',opened_at)::date as month,count(*) as orders,sum(amount_received_brl) as amount from selected_orders group by 1 having count(*)>=5 order by 1")
    monthly["month"]=pd.to_datetime(monthly["month"])
    left,right=st.columns([1.45,1])
    with left,st.container(border=True,key="panel_daily"):
        st.subheader("Movimento no período")
        metric=st.radio("Medida do gráfico",["Valor recebido","Pedidos pagos"],horizontal=True,key="sales_chart_metric")
        plot(daily,"day","amount" if metric=="Valor recebido" else "orders",x_title="Data",y_title="Valor recebido (R$)" if metric=="Valor recebido" else "Pedidos pagos")
        st.caption("Marcadores permitem ver um único dia. Lacunas = ausência ou grupo diário inferior a cinco; não representam zero.")
    with right,st.container(border=True,key="panel_monthly"):
        st.subheader("Evolução mensal")
        plot(monthly,"month","amount",x_title="Mês",y_title="Valor recebido (R$)",color=TEAL)
        st.caption("A linha mostra a evolução do valor recebido realizado nos filtros, não lucro ou projeções. Meses parciais não equivalem a meses completos.")
    channels=sq("select source_channel as channel,count(*) as orders,sum(amount_received_brl) as amount from selected_orders group by 1 having count(*)>=5 order by 3 desc")
    channels.channel=channels.channel.map(lambda x:CHANNELS.get(x,x))
    items=item_labels(sq(PRODUCTS)).sort_values("units",ascending=False).head(8)
    left,right=st.columns(2)
    with left,st.container(border=True,key="panel_channels"):
        st.subheader("Canais do recorte")
        plot(channels,"channel","amount",horizontal=True,x_title="Canal",y_title="Valor recebido (R$)")
        st.caption("Origens do PDV; relatórios sobrepostos não são somados.")
    with right,st.container(border=True,key="panel_items"):
        st.subheader("Itens mais vendidos")
        plot(items,"item_label","units",horizontal=True,color=TEAL,x_title="Item",y_title="Unidades")
        st.caption("Até oito itens presentes em cinco pedidos; componente de combo não é combo completo.")
    weekdays=sq("select (isodow(opened_at)-1)::int as weekday,count(*) as orders,sum(amount_received_brl) as amount from selected_orders group by 1 having count(*)>=5 order by 1")
    weekdays["label"]=weekdays.weekday.map(lambda x:DAYS[x])
    hours=sq("select hour(opened_at)::int as hour,count(*) as orders from selected_orders group by 1 having count(*)>=5 order by 1")
    hours["label"]=hours.hour.map(lambda x:f"{x:02d}h")
    left,right=st.columns(2)
    with left,st.container(border=True,key="panel_weekdays"):
        st.subheader("Dias de maior movimento")
        plot(weekdays,"label","amount",kind="bar",order=list(DAYS),x_title="Dia da semana",y_title="Valor recebido (R$)")
        st.caption("Soma no recorte, não média de uma semana típica.")
    with right,st.container(border=True,key="panel_hours"):
        st.subheader("Horário de entrada dos pedidos")
        plot(hours,"label","orders",kind="bar",order=hours.label.tolist(),x_title="Hora de abertura",y_title="Pedidos pagos")
        st.caption("Abertura no sistema, não preparo. Horário informado: terça a domingo, 18h30–23h.")
    with st.expander("Conferir números e semanas"):
        table(daily.rename(columns={"day":"Data","orders":"Pedidos pagos","amount":"Valor recebido (R$)"}))
        weekly=sq("select date_trunc('week',opened_at)::date as week_start,count(*) as paid_orders,sum(amount_received_brl) as amount_received_brl from selected_orders group by 1 having count(*)>=5 order by 1")
        table(weekly)
        st.caption("Semanas incluem somente datas/dimensões selecionadas; bordas podem ser parciais.")

def products(sq,table):
    frame=item_labels(sq(PRODUCTS))
    with st.container(border=True,key="panel_product_filters"):
        cols=st.columns(3)
        kind=cols[0].selectbox("Tipo de item",["Todos","Produto avulso","Complemento","Componente de combo"],key="product_kind")
        category=cols[1].selectbox("Categoria",["Todas"]+sorted(frame.product_category.dropna().unique().tolist()),key="product_category")
        rank=cols[2].selectbox("Ordenar por",["Unidades vendidas","Valor dos itens"],key="product_rank")
        if kind!="Todos": frame=frame.loc[frame.item_type.eq({"Produto avulso":"produto","Complemento":"complemento","Componente de combo":"item_de_combo"}[kind])]
        if category!="Todas": frame=frame.loc[frame.product_category.eq(category)]
    if frame.empty:
        st.info("Nenhum item com presença em cinco pedidos nos filtros.")
        return
    cols=st.columns(3)
    cols[0].metric("Itens elegíveis",len(frame))
    cols[1].metric("Unidades dos itens exibidos",f"{frame.units.sum():,.0f}".replace(",","."))
    cols[2].metric("Valor dos itens exibidos",money(frame.amount.sum()))
    field="units" if rank=="Unidades vendidas" else "amount"
    frame=frame.sort_values([field,"product_name"],ascending=[False,True])
    left,right=st.columns(2)
    for col,title,rows,color in [(left,"Maiores volumes / valores",frame.head(10),BLUE),(right,"Menores volumes / valores elegíveis",frame.tail(10).sort_values(field),AMBER)]:
        with col,st.container(border=True,key="panel_products_"+color.lstrip("#")):
            st.subheader(title)
            plot(rows,"item_label",field,horizontal=True,color=color,x_title="Item",y_title=rank,height=310,order=rows.item_label.tolist())
    st.caption("Seleções alteram cartões, gráficos e tabela. Totais só dos grupos elegíveis; valor de itens não é margem nem total recebido do pedido.")
    table(frame.drop(columns="item_label").rename(columns={"units":"units_sold","orders":"orders_containing_item","amount":"item_sales_brl"}))

def customers(sq,filters,table):
    customer_sql="select customer_key,count(*) as orders,sum(amount_received_brl) as amount from selected_orders where customer_key is not null group by 1"
    totals=sq("select count(*) as identified,count(*) filter(where orders>=2) as recurring from ("+customer_sql+") c").iloc[0]
    if int(totals.identified)<10:
        st.info("Menos de dez clientes identificáveis no recorte; amplie os filtros.")
        return
    safe=int(totals.recurring)==0 or (int(totals.recurring)>=5 and int(totals.identified-totals.recurring)>=5)
    cols=st.columns(3)
    cols[0].metric("Clientes com código válido",int(totals.identified))
    cols[1].metric("Duas ou mais compras",int(totals.recurring) if safe else "Grupo pequeno")
    cols[2].metric("Recorrência no recorte",f"{totals.recurring/totals.identified:.1%}" if safe else "Não exibida")
    groups=sq("select case when orders=1 then '1 pedido' when orders<=3 then '2–3 pedidos' when orders<=7 then '4–7 pedidos' else '8+ pedidos' end as grupo,count(*) as clientes,sum(orders) as pedidos,sum(amount) as valor_recebido from ("+customer_sql+") c group by 1 having count(*)>=5")
    left,right=st.columns(2)
    with left,st.container(border=True,key="panel_frequency"):
        st.subheader("Frequência de compras")
        plot(groups,"grupo","clientes",kind="bar",color=TEAL,x_title="Compras no recorte",y_title="Clientes")
    with right,st.container(border=True,key="panel_customer_amount"):
        st.subheader("Valor recebido por grupo")
        plot(groups,"grupo","valor_recebido",horizontal=True,x_title="Grupo",y_title="Valor recebido (R$)")
    table(groups)
    st.caption("Recorrência só das compras filtradas, não da vida do cliente. Grupos pequenos são omitidos; sem códigos individuais.")
    monthly=sq("select date_trunc('month',opened_at)::date as month,count(distinct customer_key) as customers from selected_orders where customer_key is not null group by 1 having count(distinct customer_key)>=10 order by 1")
    monthly["month"]=pd.to_datetime(monthly.month)
    with st.container(border=True,key="panel_monthly_customers"):
        st.subheader("Clientes identificáveis por mês")
        plot(monthly,"month","customers",x_title="Mês",y_title="Clientes distintos",color=TEAL)
        st.caption("Mesmo cliente pode aparecer em meses diferentes; não some os meses para obter clientes únicos.")
    with st.expander("Primeira observação, retorno mensal e tempo sem compra"):
        cohorts=sq("select date_trunc('month',o.opened_at)::date as month_start,count(distinct case when date_trunc('month',a.first_seen)=date_trunc('month',o.opened_at) then o.customer_key end) as first_seen,count(distinct case when date_trunc('month',a.first_seen)<date_trunc('month',o.opened_at) then o.customer_key end) as returning from selected_orders o join (select customer_key,min(opened_at) as first_seen from analytics.stg_orders where order_status='paid' and customer_key is not null group by 1) a using(customer_key) group by 1 having count(distinct o.customer_key)>=10 order by 1")
        for field in ("first_seen","returning"):
            cohorts.loc[(cohorts[field]>0)&(cohorts[field]<5),field]=float("nan")
        table(cohorts.rename(columns={"first_seen":"Primeira aparição no histórico","returning":"Retorno de mês anterior"}))
        recency=sq("select case when date_diff('day',last_seen,cast(? as date))<=30 then 'Até 30 dias' when date_diff('day',last_seen,cast(? as date))<=60 then '31–60 dias' else 'Mais de 60 dias' end as tempo_sem_compra,count(*) as clientes from (select customer_key,max(cast(opened_at as date)) as last_seen from selected_orders where customer_key is not null group by 1) c group by 1 having count(*)>=5",(filters.end,filters.end))
        table(recency)
        st.caption("Primeira aparição usa o histórico geral, não a primeira compra da vida. Retorno e recência incluem só clientes ativos nos filtros; recência é a última compra selecionada até a data final. Grupos pequenos não são exibidos.")

def render_private(page,manifest,root,table,raw,delivery,marketing):
    warehouse=str(root/manifest["warehouse"])
    filters=filter_bar(manifest,warehouse,page)
    if filters is None: return
    def sq(sql,parameters=(),custom=None):
        return sales_query(warehouse,manifest["run_id"],custom or filters,sql,tuple(parameters))
    if page in {"Visão geral","Produtos","Clientes"} and int(sq(SUMMARY).iloc[0].orders)<5:
        st.info("Menos de cinco pedidos pagos atendem aos filtros. Amplie o recorte ou use Limpar filtros.")
        return
    if page=="Visão geral": overview(sq,filters,manifest,table)
    elif page=="Produtos": products(sq,table)
    elif page=="Clientes": customers(sq,filters,table)
    else:
        period=(filters.start.isoformat(),filters.end.isoformat())
        if page=="Delivery": delivery(raw,period)
        elif page=="Marketing": marketing(raw,period)
