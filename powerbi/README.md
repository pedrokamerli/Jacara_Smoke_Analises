# Power BI — Jacaré Smoke House

Este diretório guarda a especificação do painel. O arquivo de dados reais e o `.pbix` devem permanecer locais e fora do Git.

## Fonte local

Use `data/private/powerbi/Jacare_Fonte_PowerBI_Real.xlsx`. O arquivo contém dados agregados e não inclui nomes, telefones, endereços ou chaves de clientes.

No Power BI Desktop, selecione **Obter dados > Excel**, carregue as sete tabelas e ignore a aba `Leia_me`.

Crie a tabela de calendário:

```DAX
Calendario =
ADDCOLUMNS (
    CALENDAR ( MIN ( Vendas_Diarias[sale_date] ), MAX ( Vendas_Diarias[sale_date] ) ),
    "Ano", YEAR ( [Date] ),
    "Mês Número", MONTH ( [Date] ),
    "Mês", FORMAT ( [Date], "mmm" ),
    "Ano-Mês", FORMAT ( [Date], "yyyy-MM" ),
    "Dia da Semana", FORMAT ( [Date], "dddd" ),
    "Dia da Semana Número", WEEKDAY ( [Date], 2 )
)
```

Renomeie a coluna `Date` para `Data` e relacione `Calendario[Data]` com `Vendas_Diarias[sale_date]`, `Vendas_Hora[sale_date]`, `Marketing_Diario[metric_date]` e `Atividade_Clientes_Mensal[month_start]`.

## Medidas

Copie as medidas de `medidas.dax`. Formate valor e ticket como moeda brasileira; crescimento e recorrência como percentual.

## Páginas do painel

### 1. Visão executiva

- Cartões: Valor Recebido, Pedidos Pagos, Ticket Médio e Crescimento Receita %.
- Linha: Valor Recebido por `Calendario[Ano-Mês]`.
- Barras: Valor Recebido por `Vendas_Canal[source_channel]`.
- Segmentadores: Ano-Mês e canal.

### 2. Produtos e operação

- Barras horizontais: Valor por Produto, Top 10.
- Barras horizontais: Unidades Vendidas, Top 10.
- Colunas: Pedidos por hora (`Vendas_Hora[hour]`).
- Matriz: categoria, produto, unidades, pedidos que contêm o item e valor dos itens.

### 3. Clientes e marketing

- Cartão: Taxa de Recorrência.
- Colunas agrupadas: primeira observação e retorno por mês.
- Linha dupla: investimento Meta Ads e Valor Recebido por data.
- Cartão: CPC Meta Ads.

## Regras de interpretação

- Valor recebido não é lucro: não há custos completos no modelo.
- Datas sem registro mantêm valores nulos; não devem virar vendas zero.
- Produtos por valor medem valor de itens, que pode divergir do valor recebido do pedido.
- Marketing e vendas no mesmo gráfico descrevem coexistência temporal, não causalidade.
- Não criar tabela nem ranking de clientes individuais.
