# Jacaré Analytics — DEMONSTRAÇÃO SINTÉTICA

Todos os valores, produtos, clientes e previsões deste pacote são fictícios e independentes do negócio real. Valor recebido não é lucro.

## 1. Faturamento recebido e pedidos

Foram recebidos R$ 316.315,00 em 5.335 pedidos pagos. Há 203 dias com registros e 34 datas sem registros no calendário.

Este é o tamanho das vendas recebidas no histórico. Sem custos de ingredientes, equipe e operação, não é possível calcular lucro.

Total Recebido não é lucro; apenas pedidos pagos. Publicação com recorte fixo: grupos pequenos são omitidos e não há filtros livres de datas.

Consulta reproduzível: `01_totals.sql`.

| first_date | last_date | paid_orders | received_brl | observed_days | missing_days |
| --- | --- | --- | --- | --- | --- |
| 2025-01-02 00:00:00 | 2025-08-26 00:00:00 | 5335.0 | 316315.0 | 203 | 34 |

## 2. Evolução mensal

O maior total mensal registrado foi R$ 46.254,00, no mês 07/2025. A tabela permite acompanhar todos os meses; as bordas do histórico são parciais.

A evolução ajuda a acompanhar o negócio. Uma barra menor em mês incompleto não comprova queda; confira quantos dias estão cobertos antes de comparar.

Meses nas bordas do histórico são parciais; não comparar como meses completos. Publicação com recorte fixo: grupos pequenos são omitidos e não há filtros livres de datas.

Consulta reproduzível: `02_monthly_evolution.sql`.

| month_start | paid_orders | received_brl | average_ticket_brl | observed_days |
| --- | --- | --- | --- | --- |
| 2025-01-01 00:00:00 | 583.0 | 34594.0 | 59.337907375643226 | 26 |
| 2025-02-01 00:00:00 | 553.0 | 32737.0 | 59.19891500904159 | 24 |
| 2025-03-01 00:00:00 | 642.0 | 38476.0 | 59.93146417445483 | 26 |
| 2025-04-01 00:00:00 | 652.0 | 38341.0 | 58.80521472392638 | 26 |
| 2025-05-01 00:00:00 | 724.0 | 42572.0 | 58.80110497237569 | 27 |
| 2025-06-01 00:00:00 | 717.0 | 41799.0 | 58.29707112970711 | 25 |
| 2025-07-01 00:00:00 | 770.0 | 46254.0 | 60.07012987012987 | 27 |
| 2025-08-01 00:00:00 | 694.0 | 41542.0 | 59.85878962536023 | 22 |

## 3. Melhores e menores dias

Maior valor: R$ 2.772,00 no dia 08/08/2025. Menor valor exibido: R$ 716,00 no dia 08/04/2025. O maior volume foi 40 pedidos no dia 15/08/2025. O menor volume exibido foi 13 pedidos no dia 08/01/2025. Empates, quando existentes, aparecem na tabela.

Use as datas para investigar promoções, eventos e capacidade de atendimento. Um pico não prova que uma ação específica causou mais vendas.

Dias com pelo menos cinco pedidos; datas sem registro não entram como vendas zero. Publicação com recorte fixo: grupos pequenos são omitidos e não há filtros livres de datas.

Consulta reproduzível: `03_best_worst_days.sql`.

| sale_date | paid_orders | amount_received_brl | highest_value_rank | lowest_value_rank | highest_volume_rank | lowest_volume_rank |
| --- | --- | --- | --- | --- | --- | --- |
| 2025-01-08 00:00:00 | 13 | 872.0 | 195 | 9 | 203 | 1 |
| 2025-04-08 00:00:00 | 16 | 716.0 | 203 | 1 | 194 | 8 |
| 2025-08-08 00:00:00 | 39 | 2772.0 | 1 | 203 | 2 | 201 |
| 2025-08-15 00:00:00 | 40 | 2347.0 | 5 | 199 | 1 | 203 |

## 4. Melhores e menores semanas

Maior valor: R$ 12.069,00 no semana iniciada em 04/08/2025. Menor valor exibido: R$ 7.669,00 no semana iniciada em 20/01/2025. O maior volume foi 198 pedidos no semana iniciada em 04/08/2025. O menor volume exibido foi 129 pedidos no semana iniciada em 20/01/2025. A semana de menor valor tem 6/7 dias com registros. Empates, quando existentes, aparecem na tabela.

Semanas ajudam no planejamento da equipe e das compras. Uma semana sem registros em alguns dias pode parecer pior apenas por falta de informação.

Semanas de segunda a domingo contidas na fonte. Dias sem registro limitam a interpretação. Publicação com recorte fixo: grupos pequenos são omitidos e não há filtros livres de datas.

Consulta reproduzível: `04_best_worst_weeks.sql`.

| week_start | paid_orders | amount_received_brl | observed_days | missing_days | highest_value_rank | lowest_value_rank | highest_volume_rank | lowest_volume_rank |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2025-01-20 00:00:00 | 129.0 | 7669.0 | 6 | 1 | 33 | 1 | 33 | 1 |
| 2025-08-04 00:00:00 | 198.0 | 12069.0 | 6 | 1 | 1 | 33 | 1 | 33 |

## 5. Dias da semana e horários

O maior valor acumulado por dia da semana foi na sexta-feira: R$ 65.086,00. A faixa das 21h concentrou 1.275 pedidos pagos, o maior volume por hora de abertura.

Os horários de maior volume podem orientar a preparação da cozinha. O total por dia da semana também depende de quantas dessas datas aparecem no arquivo.

Horário de abertura do pedido; distribuição observada, sem inferir funcionamento. Publicação com recorte fixo: grupos pequenos são omitidos e não há filtros livres de datas.

Consulta reproduzível: `05_weekdays_hours.sql`.

| dimension | value | paid_orders | received_brl |
| --- | --- | --- | --- |
| hour | 18 | 588.0 | 35339.0 |
| hour | 19 | 1208.0 | 71518.0 |
| hour | 20 | 1249.0 | 74268.0 |
| hour | 21 | 1275.0 | 74782.0 |
| hour | 22 | 1015.0 | 60408.0 |
| weekday | 2 | 774.0 | 45668.0 |
| weekday | 3 | 721.0 | 42460.0 |
| weekday | 4 | 742.0 | 45306.0 |
| weekday | 5 | 1072.0 | 65086.0 |
| weekday | 6 | 1002.0 | 58953.0 |
| weekday | 7 | 1024.0 | 58842.0 |

## 6. Ticket por canal

MenuDino — app/site apresentou o maior ticket: R$ 63,04 por pedido pago. Em quantidade de pedidos, Comanda mobile liderou com 1.365; em valor recebido, MenuDino — app/site liderou com R$ 85.292,00.

Ticket é o valor recebido dividido pelos pedidos pagos. Maior ticket não significa maior lucro nem maior número de clientes.

Origem registrada no PDV; Desktop não é uma plataforma de delivery. Publicação com recorte fixo: grupos pequenos são omitidos e não há filtros livres de datas.

Consulta reproduzível: `06_ticket_channels.sql`.

| source_channel | paid_orders | received_brl | average_ticket_brl |
| --- | --- | --- | --- |
| menudino_app_site | 1353 | 85292.0 | 63.03917220990392 |
| ifood | 1278 | 78802.0 | 61.660406885758995 |
| comanda_mobile | 1365 | 77285.0 | 56.61904761904762 |
| desktop | 1339 | 74936.0 | 55.96415235250187 |

## 7. Produtos por unidades

Líder entre os grupos exibidos: Burger Demo A (produto avulso), com 4.147 unidades, presente em 2.748 pedidos. Confira os demais grupos na tabela. Por presença em compras, o líder é Burger Demo A (produto avulso), em 2.748 pedidos.

Quantidade ajuda a priorizar estoque. O mesmo nome pode aparecer como produto avulso e como componente de combo: são grupos separados nesta resposta.

Itens de combo são componentes; a fonte consolidada não identifica o combo pai. Publicação com recorte fixo: grupos pequenos são omitidos e não há filtros livres de datas.

Consulta reproduzível: `07_top_product_units.sql`.

| product_name | product_category | item_type | units_sold | orders_containing_item | item_sales_brl |
| --- | --- | --- | --- | --- | --- |
| Burger Demo A | Categoria Demo | produto | 4147.0 | 2748 | 99528.0 |
| Bebida Demo | Categoria Demo | produto | 4008.0 | 2659 | 28056.0 |
| Burger Demo B | Categoria Demo | produto | 3998.0 | 2670 | 127936.0 |
| Batata Demo | Categoria Demo | produto | 3970.0 | 2675 | 47640.0 |

| product_name | product_category | item_type | units_sold | orders_containing_item | item_sales_brl |
| --- | --- | --- | --- | --- | --- |
| Burger Demo A | Categoria Demo | produto | 4147.0 | 2748 | 99528.0 |
| Batata Demo | Categoria Demo | produto | 3970.0 | 2675 | 47640.0 |
| Burger Demo B | Categoria Demo | produto | 3998.0 | 2670 | 127936.0 |
| Bebida Demo | Categoria Demo | produto | 4008.0 | 2659 | 28056.0 |

## 8. Produtos por valor

Líder entre os grupos exibidos: Burger Demo B (produto avulso), com R$ 127.936,00, presente em 2.670 pedidos. Confira os demais grupos na tabela.

Valor de vendas ajuda a entender a participação dos itens no negócio. Não é uma lista dos mais lucrativos, pois não temos custos.

Valor dos itens registrado; não mede margem e não precisa coincidir com Total Recebido. Publicação com recorte fixo: grupos pequenos são omitidos e não há filtros livres de datas.

Consulta reproduzível: `08_top_product_value.sql`.

| product_name | product_category | item_type | units_sold | orders_containing_item | item_sales_brl |
| --- | --- | --- | --- | --- | --- |
| Burger Demo B | Categoria Demo | produto | 3998.0 | 2670 | 127936.0 |
| Burger Demo A | Categoria Demo | produto | 4147.0 | 2748 | 99528.0 |
| Batata Demo | Categoria Demo | produto | 3970.0 | 2675 | 47640.0 |
| Bebida Demo | Categoria Demo | produto | 4008.0 | 2659 | 28056.0 |

## 9. Produtos com menor volume

Menor volume entre os grupos exibidos: Batata Demo (produto avulso), com 3.970 unidades, presente em 2.675 pedidos. Confira os demais grupos na tabela.

Baixo volume é um sinal para investigar disponibilidade, tempo no cardápio e exposição. Não é motivo suficiente para excluir um produto.

Grupos de pelo menos cinco pedidos. Volume baixo não determina retirada do cardápio. Publicação com recorte fixo: grupos pequenos são omitidos e não há filtros livres de datas.

Consulta reproduzível: `09_low_product_volume.sql`.

| product_name | product_category | item_type | units_sold | orders_containing_item | item_sales_brl |
| --- | --- | --- | --- | --- | --- |
| Batata Demo | Categoria Demo | produto | 3970.0 | 2675 | 47640.0 |
| Burger Demo B | Categoria Demo | produto | 3998.0 | 2670 | 127936.0 |
| Bebida Demo | Categoria Demo | produto | 4008.0 | 2659 | 28056.0 |
| Burger Demo A | Categoria Demo | produto | 4147.0 | 2748 | 99528.0 |

## 10. Complementos

Não há grupos elegíveis para esta resposta nos arquivos desta geração.

Os complementos indicam preferências e oportunidades de oferta. A frequência de compra não informa a margem desses adicionais.

Classificação item_type da fonte, sem custos. Publicação com recorte fixo: grupos pequenos são omitidos e não há filtros livres de datas.

Consulta reproduzível: `10_complements.sql`.

Sem grupos elegíveis para publicação.

## 11. Grupos de clientes com maior valor

O grupo de 8+ pedidos tem o maior valor médio acumulado: R$ 680,25 por cliente. São 426 clientes nesse grupo.

Em vez de divulgar os melhores clientes individualmente, comparo grupos de frequência. Isso mostra o valor da fidelização sem expor pessoas.

Faixas de frequência com pelo menos cinco clientes; nenhum cliente é exposto individualmente. Publicação com recorte fixo: grupos pequenos são omitidos e não há filtros livres de datas.

Consulta reproduzível: `11_customer_groups.sql`.

| frequency_group | customers | orders | received_brl | average_received_per_customer |
| --- | --- | --- | --- | --- |
| 8+ pedidos | 426 | 4893.0 | 289788.0 | 680.2535211267606 |
| 4-7 pedidos | 72 | 436.0 | 26221.0 | 364.18055555555554 |

## 12. Recorrência

Dos 500 clientes reconhecíveis por código protegido, 500 compraram duas ou mais vezes: 100,0%. A análise cobre 5.335 pedidos pagos com código válido.

Recorrência significa duas ou mais compras no histórico analisado. A taxa vale somente para clientes que podem ser reconhecidos por um código protegido.

Somente pedidos com telefone válido pseudonimizado. Clientes sem chave não são classificados como únicos. Publicação com recorte fixo: grupos pequenos são omitidos e não há filtros livres de datas.

Consulta reproduzível: `12_recurrence.sql`.

| identified_customers | recurring_customers | recurrence_rate | identified_paid_orders |
| --- | --- | --- | --- |
| 500 | 500 | 1.0 | 5335.0 |

## 13. Primeira observação, retorno e recência

No último mês do histórico (08/2025), 0 clientes apareceram pela primeira vez nos arquivos e 363 já tinham aparecido em meses anteriores. A segunda tabela mostra o tempo desde a última compra observada.

Retorno indica alguém já visto em mês anterior. Tempo sem compra é medido até o fim do arquivo, não até hoje; ausência neste canal não prova abandono do negócio.

Primeira observação não é primeira compra na vida. Recência usa a última data da fonte. Publicação com recorte fixo: grupos pequenos são omitidos e não há filtros livres de datas.

Consulta reproduzível: `13_customer_lifecycle.sql`.

| month_start | identified_customers | first_seen_customers | returning_customers | identified_paid_orders | received_brl |
| --- | --- | --- | --- | --- | --- |
| 2025-01-01 00:00:00 | 344 | 344 | 0 | 583.0 | 34594.0 |
| 2025-02-01 00:00:00 | 338 | 101 | 237 | 553.0 | 32737.0 |
| 2025-03-01 00:00:00 | 364 | 40 | 324 | 642.0 | 38476.0 |
| 2025-04-01 00:00:00 | 362 | 12 | 350 | 652.0 | 38341.0 |
| 2025-06-01 00:00:00 | 396 | 0 | 396 | 717.0 | 41799.0 |
| 2025-07-01 00:00:00 | 395 | 0 | 395 | 770.0 | 46254.0 |
| 2025-08-01 00:00:00 | 363 | 0 | 363 | 694.0 | 41542.0 |

| recency_group | customers |
| --- | --- |
| Mais de 60 dias | 23 |
| 31-60 dias | 89 |
| Até 30 dias | 388 |

## 14. Canais e delivery

Na base principal, iFood: 1.278 pedidos e R$ 78.802,00; MenuDino: 1.353 pedidos e R$ 85.292,00. O arquivo separado do 99Food registra 2.013 pedidos em 203 dias com registros, de 02/01/2025 a 26/08/2025; não é uma comparação equivalente ao período completo.

Compare canais na mesma base e no mesmo período. Relatórios de plataformas podem repetir pedidos do sistema de vendas, por isso não são adicionados ao total principal.

PDV, AppDelivery, iFood_App e 99Food são apresentados em recortes próprios e não somados. Publicação com recorte fixo: grupos pequenos são omitidos e não há filtros livres de datas.

Consulta reproduzível: `14_delivery.sql`.

| source_channel | paid_orders | received_brl |
| --- | --- | --- |
| ifood | 1278 | 78802.0 |
| menudino_app_site | 1353 | 85292.0 |

| comparable_days | same_count_days | items_difference_brl |
| --- | --- | --- |
| 203 | 203 | 0.0 |

| orders | covered_days | first_order_date | last_order_date | sales_revenue_brl | shop_revenue_brl | commission_expense_brl | payment_channel_fee_brl | orders_with_both_timestamps | late_preparation_orders | average_prep_minutes | average_acceptance_seconds | average_finalization_seconds |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2013.0 | 203 | 2025-01-02 00:00:00 | 2025-08-26 00:00:00 | 70455.0 | 56364.0 | 14091.0 | 0.0 | 0.0 | 203.0 | 20.0 | 30.0 | 900.0 |

| reported_dates | reported_orders | pdv_paid_orders | matching_dates |
| --- | --- | --- | --- |
| 203 | 1278.0 | 1278.0 | 202 |

| month_start | delivery_type | order_status | orders | items_value_brl | delivery_fee_brl | first_date | last_date |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 2025-01-01 00:00:00 | delivery | entregue | 141.0 | 8321.0 | 705.0 | 2025-01-02 00:00:00 | 2025-01-31 00:00:00 |
| 2025-02-01 00:00:00 | delivery | entregue | 138.0 | 8431.0 | 690.0 | 2025-02-01 00:00:00 | 2025-02-28 00:00:00 |
| 2025-03-01 00:00:00 | delivery | entregue | 165.0 | 9196.0 | 825.0 | 2025-03-01 00:00:00 | 2025-03-30 00:00:00 |
| 2025-04-01 00:00:00 | delivery | entregue | 157.0 | 9311.0 | 785.0 | 2025-04-01 00:00:00 | 2025-04-30 00:00:00 |
| 2025-05-01 00:00:00 | delivery | entregue | 189.0 | 11109.0 | 945.0 | 2025-05-01 00:00:00 | 2025-05-31 00:00:00 |
| 2025-06-01 00:00:00 | delivery | entregue | 185.0 | 10512.0 | 925.0 | 2025-06-01 00:00:00 | 2025-06-29 00:00:00 |
| 2025-07-01 00:00:00 | delivery | entregue | 203.0 | 11960.0 | 1015.0 | 2025-07-01 00:00:00 | 2025-07-31 00:00:00 |
| 2025-08-01 00:00:00 | delivery | entregue | 175.0 | 9687.0 | 875.0 | 2025-08-01 00:00:00 | 2025-08-26 00:00:00 |

## 15. Instagram e Meta Ads

Há 6 séries de indicadores do Instagram. Seus valores são mostrados como exportados, sem inventar totais ou interpretar 'seguidores' como tamanho da base. No Meta Ads, o gasto foi R$ 2.558,00, com 255.005 impressões e 5.562 cliques no link.

Anúncios mostram gasto, exibições e cliques; Instagram mostra as séries exportadas. Sem ligar um anúncio a um pedido, não podemos afirmar quantas vendas vieram dele.

Instagram não é somado. Gasto de Meta é reconciliado com o total geral; correlação não demonstra causalidade. Publicação com recorte fixo: grupos pequenos são omitidos e não há filtros livres de datas.

Consulta reproduzível: `15_marketing.sql`.

| metric_key | observations | first_date | last_date | first_value | last_value |
| --- | --- | --- | --- | --- | --- |
| reach | 203 | 2025-01-02 00:00:00 | 2025-08-26 00:00:00 | 443.0 | 485.0 |
| views | 203 | 2025-01-02 00:00:00 | 2025-08-26 00:00:00 | 264.0 | 348.0 |
| link_clicks | 203 | 2025-01-02 00:00:00 | 2025-08-26 00:00:00 | 53.0 | 327.0 |
| content_interactions | 203 | 2025-01-02 00:00:00 | 2025-08-26 00:00:00 | 358.0 | 448.0 |
| profile_visits | 203 | 2025-01-02 00:00:00 | 2025-08-26 00:00:00 | 93.0 | 345.0 |
| followers | 203 | 2025-01-02 00:00:00 | 2025-08-26 00:00:00 | 119.0 | 119.0 |

| spend_brl | impressions | link_clicks | link_clicks_missing_rows | cpc_brl | link_ctr |
| --- | --- | --- | --- | --- | --- |
| 2558.0 | 255005.0 | 5562.0 | 0.0 | 0.45990650845019776 | 0.021811337032607205 |

| paired_dates | descriptive_correlation |
| --- | --- |
| 203 | -0.051042579709740236 |

