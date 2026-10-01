"""Narrativas calculadas a partir das respostas SQL reais, sem números fixos."""

from __future__ import annotations

import pandas as pd


QUESTION_TITLES = [
    "Quanto recebemos e quantos pedidos foram pagos?",
    "Como o valor recebido evoluiu mês a mês?",
    "Quais foram os melhores e menores dias de vendas?",
    "Quais foram as melhores e menores semanas?",
    "Em quais dias da semana e horários se concentram as vendas?",
    "Qual canal tem o maior valor médio por pedido?",
    "Quais itens mais venderam em quantidade?",
    "Quais itens geraram maior valor de vendas?",
    "Quais itens tiveram menor volume registrado?",
    "Quais complementos foram mais vendidos?",
    "Quais grupos de clientes têm maior valor de compras?",
    "Quantos clientes compraram mais de uma vez?",
    "Como aparecem os retornos e o tempo sem comprar?",
    "Como estão os canais de delivery?",
    "O que os dados mostram sobre Instagram e anúncios?",
]

INTERPRETATIONS = [
    "Este é o tamanho das vendas recebidas no histórico. Sem custos de ingredientes, equipe e operação, não é possível calcular lucro.",
    "A evolução ajuda a acompanhar o negócio. Uma barra menor em mês incompleto não comprova queda; confira quantos dias estão cobertos antes de comparar.",
    "Use as datas para investigar promoções, eventos e capacidade de atendimento. Um pico não prova que uma ação específica causou mais vendas.",
    "Semanas ajudam no planejamento da equipe e das compras. Uma semana sem registros em alguns dias pode parecer pior apenas por falta de informação.",
    "Os horários de maior volume podem orientar a preparação da cozinha. O total por dia da semana também depende de quantas dessas datas aparecem no arquivo.",
    "Ticket é o valor recebido dividido pelos pedidos pagos. Maior ticket não significa maior lucro nem maior número de clientes.",
    "Quantidade ajuda a priorizar estoque. O mesmo nome pode aparecer como produto avulso e como componente de combo: são grupos separados nesta resposta.",
    "Valor de vendas ajuda a entender a participação dos itens no negócio. Não é uma lista dos mais lucrativos, pois não temos custos.",
    "Baixo volume é um sinal para investigar disponibilidade, tempo no cardápio e exposição. Não é motivo suficiente para excluir um produto.",
    "Os complementos indicam preferências e oportunidades de oferta. A frequência de compra não informa a margem desses adicionais.",
    "Em vez de divulgar os melhores clientes individualmente, comparo grupos de frequência. Isso mostra o valor da fidelização sem expor pessoas.",
    "Recorrência significa duas ou mais compras no histórico analisado. A taxa vale somente para clientes que podem ser reconhecidos por um código protegido.",
    "Retorno indica alguém já visto em mês anterior. Tempo sem compra é medido até o fim do arquivo, não até hoje; ausência neste canal não prova abandono do negócio.",
    "Compare canais na mesma base e no mesmo período. Relatórios de plataformas podem repetir pedidos do sistema de vendas, por isso não são adicionados ao total principal.",
    "Anúncios mostram gasto, exibições e cliques; Instagram mostra as séries exportadas. Sem ligar um anúncio a um pedido, não podemos afirmar quantas vendas vieram dele.",
]


def br_number(value: float, decimals: int = 0) -> str:
    return f"{value:,.{decimals}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def money(value: float) -> str:
    return "R$ " + br_number(value, 2)


def short_date(value) -> str:
    return pd.Timestamp(value).strftime("%d/%m/%Y")


def answer_summary(answer: dict) -> str:
    """Resumir somente os registros devolvidos pelas consultas da geração ativa."""
    number = answer["id"]
    sets = answer["results"]
    rows = sets[0] if sets else []
    if not rows:
        return "Não há grupos elegíveis para esta resposta nos arquivos desta geração."
    row = rows[0]
    if number == 1:
        return f"Foram recebidos {money(row['received_brl'])} em {br_number(row['paid_orders'])} pedidos pagos. Há {row['observed_days']} dias com registros e {row['missing_days']} datas sem registros no calendário."
    if number == 2:
        top = max(rows, key=lambda r: r["received_brl"])
        return f"O maior total mensal registrado foi {money(top['received_brl'])}, no mês {pd.Timestamp(top['month_start']):%m/%Y}. A tabela permite acompanhar todos os meses; as bordas do histórico são parciais."
    if number in (3, 4):
        high = next((r for r in rows if r["highest_value_rank"] == 1), None)
        low = next((r for r in rows if r["lowest_value_rank"] == 1), None)
        key = "sale_date" if number == 3 else "week_start"
        unit = "dia" if number == 3 else "semana iniciada em"
        text = f"Maior valor: {money(high['amount_received_brl'])} no {unit} {short_date(high[key])}. Menor valor exibido: {money(low['amount_received_brl'])} no {unit} {short_date(low[key])}." if high and low else "Confira os rankings disponíveis na tabela."
        volume = next((r for r in rows if r["highest_volume_rank"] == 1), None)
        if volume:
            text += f" O maior volume foi {br_number(volume['paid_orders'])} pedidos no {unit} {short_date(volume[key])}."
        low_volume = next((r for r in rows if r["lowest_volume_rank"] == 1), None)
        if low_volume:
            text += f" O menor volume exibido foi {br_number(low_volume['paid_orders'])} pedidos no {unit} {short_date(low_volume[key])}."
        if number == 4 and low:
            text += f" A semana de menor valor tem {low['observed_days']}/7 dias com registros."
        return text + " Empates, quando existentes, aparecem na tabela."
    if number == 5:
        weekdays = [r for r in rows if r["dimension"] == "weekday"]
        hours = [r for r in rows if r["dimension"] == "hour"]
        parts = []
        if weekdays:
            best = max(weekdays, key=lambda r: r["received_brl"])
            name = {1:"segunda-feira",2:"terça-feira",3:"quarta-feira",4:"quinta-feira",5:"sexta-feira",6:"sábado",7:"domingo"}[int(best["value"])]
            parts.append(f"O maior valor acumulado por dia da semana foi na {name}: {money(best['received_brl'])}.")
        if hours:
            best = max(hours, key=lambda r: r["paid_orders"])
            parts.append(f"A faixa das {int(best['value']):02d}h concentrou {br_number(best['paid_orders'])} pedidos pagos, o maior volume por hora de abertura.")
        return " ".join(parts)
    if number == 6:
        best = max(rows, key=lambda r: r["average_ticket_brl"])
        name = {"desktop":"Desktop (origem no sistema de vendas)","comanda_mobile":"Comanda mobile","ifood":"iFood","menudino_app_site":"MenuDino — app/site"}.get(best["source_channel"],best["source_channel"])
        highest_orders=max(rows,key=lambda r:r["paid_orders"])
        highest_value=max(rows,key=lambda r:r["received_brl"])
        channels={"desktop":"Desktop (origem no sistema de vendas)","comanda_mobile":"Comanda mobile","ifood":"iFood","menudino_app_site":"MenuDino — app/site"}
        return f"{name} apresentou o maior ticket: {money(best['average_ticket_brl'])} por pedido pago. Em quantidade de pedidos, {channels.get(highest_orders['source_channel'],highest_orders['source_channel'])} liderou com {br_number(highest_orders['paid_orders'])}; em valor recebido, {channels.get(highest_value['source_channel'],highest_value['source_channel'])} liderou com {money(highest_value['received_brl'])}."
    if number in (7, 8, 9, 10):
        field = "item_sales_brl" if number == 8 else "units_sold"
        best = (min if number == 9 else max)(rows, key=lambda r: r[field])
        kind = {"produto":"produto avulso","item_de_combo":"componente de combo","complemento":"complemento"}.get(best.get("item_type"),"complemento")
        quantity = money(best[field]) if number == 8 else f"{br_number(best[field])} unidades"
        scope = "Menor volume entre os grupos exibidos" if number == 9 else "Líder entre os grupos exibidos"
        text = f"{scope}: {best['product_name']} ({kind}), com {quantity}, presente em {br_number(best['orders_containing_item'])} pedidos. Confira os demais grupos na tabela."
        if number == 7 and len(sets) > 1 and sets[1]:
            presence = max(sets[1], key=lambda r:r["orders_containing_item"])
            presence_kind = {"produto":"produto avulso", "item_de_combo":"componente de combo", "complemento":"complemento"}.get(presence["item_type"],presence["item_type"])
            text += f" Por presença em compras, o líder é {presence['product_name']} ({presence_kind}), em {br_number(presence['orders_containing_item'])} pedidos."
        return text
    if number == 11:
        best = max(rows, key=lambda r: r["average_received_per_customer"])
        return f"O grupo de {best['frequency_group']} tem o maior valor médio acumulado: {money(best['average_received_per_customer'])} por cliente. São {br_number(best['customers'])} clientes nesse grupo."
    if number == 12:
        return f"Dos {br_number(row['identified_customers'])} clientes reconhecíveis por código protegido, {br_number(row['recurring_customers'])} compraram duas ou mais vezes: {br_number(row['recurrence_rate'] * 100, 1)}%. A análise cobre {br_number(row['identified_paid_orders'])} pedidos pagos com código válido."
    if number == 13:
        latest = max(rows, key=lambda r: r["month_start"])
        return f"No último mês do histórico ({pd.Timestamp(latest['month_start']):%m/%Y}), {br_number(latest['first_seen_customers'])} clientes apareceram pela primeira vez nos arquivos e {br_number(latest['returning_customers'])} já tinham aparecido em meses anteriores. A segunda tabela mostra o tempo desde a última compra observada."
    if number == 14:
        text = "Na base principal, " + "; ".join(f"{r['source_channel'].replace('menudino_app_site', 'MenuDino').replace('ifood','iFood')}: {br_number(r['paid_orders'])} pedidos e {money(r['received_brl'])}" for r in rows) + "."
        if len(sets) > 2 and sets[2] and sets[2][0].get("orders"):
            food = sets[2][0]
            text += f" O arquivo separado do 99Food registra {br_number(food['orders'])} pedidos em {food['covered_days']} dias com registros, de {short_date(food['first_order_date'])} a {short_date(food['last_order_date'])}; não é uma comparação equivalente ao período completo."
        return text
    if number == 15:
        text = f"Há {len(rows)} séries de indicadores do Instagram. Seus valores são mostrados como exportados, sem inventar totais ou interpretar 'seguidores' como tamanho da base."
        if len(sets) > 1 and sets[1] and sets[1][0].get("spend_brl") is not None:
            ads = sets[1][0]
            text += f" No Meta Ads, o gasto foi {money(ads['spend_brl'])}, com {br_number(ads['impressions'])} impressões e {br_number(ads['link_clicks'])} cliques no link."
            if ads.get("link_clicks_missing_rows"):
                text += f" O total de cliques é parcial: {br_number(ads['link_clicks_missing_rows'])} linhas de anúncios não informam essa métrica. Valores ausentes não foram substituídos por zero; CPC e CTR gerais não são calculados."
        return text
    raise ValueError("Pergunta sem narrativa definida.")
