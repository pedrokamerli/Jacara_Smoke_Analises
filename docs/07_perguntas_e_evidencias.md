# Perguntas, consultas e limites

As 15 consultas são executadas pelo pipeline e geram respostas locais em cada atualização. Elas usam o histórico completo da geração; o dashboard oferece filtros nas visualizações.

Todas as respostas também aparecem na tela **15 perguntas e respostas**. É possível ver todas ou selecionar uma pergunta. Cada seção apresenta uma narrativa calculada sobre o resultado SQL da geração ativa, sua interpretação em linguagem simples, limitações e tabelas para conferência. Esta tela usa o histórico completo, explicitamente informado, e não recebe o filtro das telas analíticas. Os números não são escritos manualmente na narrativa e acompanham novas importações.

| Pergunta do README | Consulta em sql/business | Tela | Limite |
|---|---|---|---|
| 1. Valor e pedidos | 01_totals.sql | Visão geral | Status pago e valor recebido |
| 2. Evolução | 02_monthly_evolution.sql | Visão geral | Meses parciais identificados |
| 3. Dias | 03_best_worst_days.sql | Visão geral | Pelo menos cinco pedidos; dias sem registro não são zeros |
| 4. Semanas | 04_best_worst_weeks.sql | Visão geral | Sete datas contidas na fonte, cobertura operacional pendente |
| 5. Dias/horários | 05_weekdays_hours.sql | Visão geral | Hora de abertura, não preparo/entrega |
| 6. Ticket/canais | 06_ticket_channels.sql | Visão geral | Origem registrada; ticket recebido |
| 7. Unidades | 07_top_product_units.sql | Produtos | Componentes de combos, não contagem de combos completos |
| 8. Valor por produto | 08_top_product_value.sql | Produtos | Valor dos itens, sem margem |
| 9. Menor volume | 09_low_product_volume.sql | Produtos | Grupos elegíveis; disponibilidade/cardápio não conhecidos |
| 10. Complementos | 10_complements.sql | Produtos | Classificação da fonte |
| 11. Clientes de maior valor | 11_customer_groups.sql | Clientes | Grupos de frequência, sem identificar pessoas |
| 12. Recorrência | 12_recurrence.sql | Clientes | Cobertura de telefone válido pseudonimizado |
| 13. Ciclo de vida | 13_customer_lifecycle.sql | Clientes | Primeira observação na fonte e referência no fim do histórico |
| 14. Delivery | 14_delivery.sql | Delivery | Recortes próprios e sobreposição; não somar plataformas cegamente |
| 15. Redes/marketing | 15_marketing.sql | Marketing | Sem somar séries de definição desconhecida nem afirmar causalidade |

O relatório não responde quem é uma pessoa nem calcula margem. A adaptação da pergunta de melhores clientes para grupos preserva a regra de privacidade. Nenhum zero é criado para uma venda ausente. Se não houver grupos elegíveis, a resposta fica explicitamente sem dados suficientes.

Machine Learning é uma entrega adicional: `ml/forecast_metrics.json`, modelos locais, backtest e tela própria. Aprovação operacional permanece condicionada à qualidade e atualidade da fonte, com critérios documentados.
