"""Executa as 15 perguntas em SQL e grava somente respostas agregadas locais."""

from __future__ import annotations

import json
from pathlib import Path

import duckdb
import pandas as pd

QUESTIONS = [
    ("Faturamento recebido e pedidos", "Total Recebido não é lucro; apenas pedidos pagos."),
    ("Evolução mensal", "Meses nas bordas do histórico são parciais; não comparar como meses completos."),
    ("Melhores e menores dias", "Dias com pelo menos cinco pedidos; datas sem registro não entram como vendas zero."),
    ("Melhores e menores semanas", "Semanas de segunda a domingo contidas na fonte. Dias sem registro limitam a interpretação."),
    ("Dias da semana e horários", "Horário de abertura do pedido; distribuição observada, sem inferir funcionamento."),
    ("Ticket por canal", "Origem registrada no PDV; Desktop não é uma plataforma de delivery."),
    ("Produtos por unidades", "Itens de combo são componentes; a fonte consolidada não identifica o combo pai."),
    ("Produtos por valor", "Valor dos itens registrado; não mede margem e não precisa coincidir com Total Recebido."),
    ("Produtos com menor volume", "Grupos de pelo menos cinco pedidos. Volume baixo não determina retirada do cardápio."),
    ("Complementos", "Classificação item_type da fonte, sem custos."),
    ("Grupos de clientes com maior valor", "Faixas de frequência com pelo menos cinco clientes; nenhum cliente é exposto individualmente."),
    ("Recorrência", "Somente pedidos com telefone válido pseudonimizado. Clientes sem chave não são classificados como únicos."),
    ("Primeira observação, retorno e recência", "Primeira observação não é primeira compra na vida. Recência usa a última data da fonte."),
    ("Canais e delivery", "PDV, AppDelivery, iFood_App e 99Food são apresentados em recortes próprios e não somados."),
    ("Instagram e Meta Ads", "Instagram não é somado. Gasto de Meta é reconciliado com o total geral; correlação não demonstra causalidade."),
]


def write_business_report(warehouse: Path, sql_dir: Path, output_dir: Path) -> None:
    files = sorted(sql_dir.glob("*.sql"))
    if len(files) != len(QUESTIONS):
        raise ValueError("São necessárias exatamente 15 consultas de negócio versionadas.")
    answers = []
    lines = ["# Respostas às perguntas de negócio", "", "Resultados locais agregados da geração atual. Cada resposta inclui sua definição e limitação.", ""]
    with duckdb.connect(str(warehouse), read_only=True) as connection:
        for index,(sql_file,(question,note)) in enumerate(zip(files,QUESTIONS),start=1):
            results = []
            lines.extend([f"## {index}. {question}", "", note, "", f"SQL: `{sql_file.name}`", ""])
            for sql in sql_file.read_text(encoding="utf-8").split(";"):
                if not sql.strip():
                    continue
                frame = connection.execute(sql).df()
                clean = frame.astype(object).where(pd.notna(frame),None)
                results.append(clean.to_dict(orient="records"))
                if frame.empty:
                    lines.extend(["Sem grupos elegíveis nesta fonte.", ""])
                else:
                    headers = list(frame.columns)
                    lines.append("| " + " | ".join(headers) + " |")
                    lines.append("| " + " | ".join("---" for _ in headers) + " |")
                    for row in clean.itertuples(index=False,name=None):
                        lines.append("| " + " | ".join(str(value).replace("|","\\|").replace("\n"," ") if value is not None else "—" for value in row) + " |")
                    lines.append("")
            answers.append({"id":index,"question":question,"sql":sql_file.name,"limitation":note,"results":results})
    output_dir.mkdir(parents=True,exist_ok=True)
    (output_dir / "analysis_report.md").write_text("\n".join(lines),encoding="utf-8")
    (output_dir / "analysis_results.json").write_text(json.dumps(answers,ensure_ascii=False,default=str,allow_nan=False,indent=2),encoding="utf-8")
