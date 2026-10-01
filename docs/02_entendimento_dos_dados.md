# CRISP-DM | 2. Entendimento dos dados

**Status:** levantamento inicial feito em 30/09/2026. O inventário usa nomes de arquivos, abas e cabeçalhos; não reproduz registros de clientes.

## Pacotes encontrados

| Pacote | Conteúdo identificado | Observação |
|---|---|---|
| `JACARE_SMOKE_HOUSE_PEDIDOS_E_RELATORIOS_ORGANIZADOS_2026.zip` | Pedidos consolidados, itens, clientes, delivery, Meta Ads, snapshots, tabelas derivadas e relatórios | Fonte principal para a primeira versão; contém dados pessoais em algumas planilhas. |
| `jacare anaise perfil.zip` | Exportações de Instagram e um ZIP interno com dados brutos e relatórios | Há fontes repetidas e janelas que se sobrepõem ao pacote principal. |

Os pacotes e as pastas extraídas pelo usuário permanecem como fontes locais. O pipeline lê os arquivos existentes ou os ZIPs em memória; não copia identificadores pessoais para os artefatos analíticos publicados pela aplicação.

## Fontes prioritárias e granularidade esperada

| Fonte | Aba | Granularidade esperada | Campos relevantes observados | Cuidados |
|---|---|---|---|---|
| `01_Todos_os_pedidos_01-01_a_20-08-2026.xlsx` | `Sheet` | Um registro por pedido | Código, Data Abertura, Status, Tipo, Origem, Data Fechamento, Tot. Itens, Serviço, Valor Entrega, Total, Total Recebido, forma de pagamento e UTM | Também contém cliente, telefone, endereço, observações e colunas extras de navegação. Dia 20/08 é parcial; baseline de período fechado até 19/08. |
| `02_Historico_Itens_Vendidos_01-01_a_20-08-2026.xlsx` | `Sheet` | Um registro por item do pedido | Data/Hora Item, Qtd., Valor Un. Item, Valor. Tot. Item, Tipo de Item, Nome Prod, Tipo Prod, Cat. Prod., Cod. Ped., datas e status do pedido | Juntar a pedidos por `Cod. Ped.` após validar tipos, chaves e duplicidade. A granularidade é diferente da planilha de pedidos. |
| `03_Lista_Clientes_20-08-2026.xlsx` | `Sheet` | Um registro por cliente cadastrado | Qtd. Pedidos, Últ. Pedido, origem e campos demográficos | Tem nome, telefones, endereço, e-mail, aniversário, data de nascimento e CEP. Não publicar nem usar identificadores diretos nos marts. |
| `04_PEDIDOS_HISTORICOS.xlsx` | `Sheet` | Registro histórico de pedido | Campos semelhantes à base consolidada | Pode sobrepor a base consolidada; não somar até identificar intervalo e unicidade por código. |
| `Pedidos_AppDelivery_01-01_a_04-08-2026.xlsx` | `Sheet` | Um registro por pedido do AppDelivery | Id, Criado em, Valor Itens, Valor Entrega, Tipo de Entrega, Status | Período parcial e possivelmente já contido na base consolidada. Usar para reconciliação ou métricas operacionais específicas. |
| Export 99Food de julho/2026 | `Sheet1` | Um registro por pedido | ID do pedido, horários, receita, quantidade, status, entrega, preparo, cancelamento, avaliação, comissão, taxas, despesas com ofertas e custos logísticos | Inclui IDs de cliente/loja, nome e conteúdo de avaliação. Existem custos específicos do canal que podem apoiar análise de deduções do 99Food após validação; não são CMV nem custos completos do negócio. Confirmar significado/moeda e remover identificadores. |
| Relatórios Meta Ads | `Formatted Report`, `Raw Data Report` | Linha agregada conforme nível e período do relatório | Campanha, datas, gasto, impressões, alcance, cliques, resultados, compras e métricas de conversão | Existem layouts diferentes e sobreposição de datas. Não unir relatórios agregados como se fossem eventos diários; selecionar um relatório canônico por período e nível. |
| CSVs de Instagram | Varia por métrica | Uma observação por data em alguns arquivos; outros trazem métricas por publicação/story | Alcance, interações, cliques no link, seguidores, visitas ao perfil, visualizações e dados de posts | Alguns arquivos começam com `sep=,` e usam UTF-16. Os exports por publicação contêm IDs de post/conta, descrição e links; revisar esses campos antes de compartilhar. Validar cabeçalho, datas e se os valores são diários ou acumulados. |

## Relações candidatas

- Pedidos ↔ itens: `Código` ↔ `Cod. Ped.`; validar zeros à esquerda, espaços e cardinalidade antes de agregar.
- Pedidos ↔ cadastro de clientes: a extração consultada não mostrou uma chave estável e livre de ambiguidade. Nome/telefone não será tratado como chave analítica pública. Medir cobertura e duplicidade antes de definir identidade de cliente.
- Vendas ↔ Meta/Instagram: UTM pode permitir recortes identificáveis em alguns pedidos. Sem identificador compatível, comparar períodos como associação temporal, sem alegar causalidade.
- Pedidos gerais ↔ plataformas de delivery: conciliar por data, ID e valor apenas depois de entender se as exportações estão incluídas na base geral.

## Evidência inicial de reconciliação de delivery

O canal iFood está presente no PDV e em relatório adicional com recorte próprio. O pipeline compara contagens diárias sem somar as fontes. O período da tabela de produtos não herda automaticamente a janela de pedidos. Resultados comerciais da reconciliação ficam privados.

O AppDelivery é agregado por data, tipo e status e comparado ao MenuDino no PDV. Igualdade de contagens não prova identidade pedido a pedido; as fontes não são somadas e a hipótese depende de confirmação da operação.

O 99Food tem cobertura própria. Registros com conclusão e cancelamento simultâneos não são classificados automaticamente como cancelados. Amostras pequenas não sustentam comparações representativas; médias com poucos registros ficam ocultas.

## Riscos e validações a executar na preparação

1. Comparar unicidade e intervalos de `Código` nas bases consolidadas, históricas e snapshots; evitar dupla contagem.
2. Identificar status que representam pedido pago/concluído, cancelado, em andamento ou fiado; definir o universo de vendas com base na regra validada.
3. Comparar `Total`, `Total Recebido`, soma dos itens, serviço e entrega para entender diferenças, descontos e pagamentos parciais.
4. Confirmar se a linha de item inclui adicionais e como kits/combos estão representados.
5. Padronizar tipos, origens e canais que aparecem com espaços, variações de nome e integrações.
6. Interpretar datas Excel numéricas, datas textuais, timezone e datas de fechamento; identificar dias incompletos.
7. Validar chaves e duplicidades de cliente antes de medir recorrência. Usar identificador pseudonimizado apenas na camada privada local, se houver base legal e necessidade analítica.
8. Tratar arquivos de marketing com cabeçalhos distintos como fontes separadas até harmonizar métrica, nível de agregação, período e atribuição.
9. Ler Instagram com detecção de BOM/codificação e pular a linha `sep=,` quando existir.
10. Excluir campos pessoais e observações livres antes de criar qualquer saída analítica compartilhável.

## Definições a confirmar antes dos indicadores

- **Faturamento:** selecionar entre `Total` e `Total Recebido` depois de reconciliar status e diferenças; não somar os dois.
- **Dia da venda:** definir se usa abertura ou fechamento do pedido e manter a mesma regra em todas as comparações.
- **Melhores/piores dias e semanas:** usar períodos completos e definir se o ranking é por faturamento, pedidos ou ambos.
- **Cliente recorrente:** cliente identificável com pelo menos dois pedidos válidos no intervalo escolhido; a taxa depende da cobertura de identificação.
- **Produto fraco:** baixo volume observado não significa baixa rentabilidade ou motivo para remoção; não há custos e pode haver efeito de disponibilidade/cardápio.
- **Melhor canal:** comparar janela coberta e população de pedidos compatíveis, incluindo plataformas sem duplicar pedidos. Para 99Food, separar faturamento bruto de receita da loja após taxas/custos informados pela plataforma.
- **Métricas sociais:** esclarecer se são somas diárias, valores acumulados ou snapshots antes de agregar.

## Próximo passo CRISP-DM

Confirmar com a operação se o canal MenuDino no PDV e o AppDelivery refletem os mesmos pedidos; validar a cobertura do calendário de funcionamento e fechar as definições de faturamento antes de avançar para previsões operacionais. As saídas compartilháveis permanecem agregadas e omitem dados pessoais.

## Preparação e avaliação implementadas

O pipeline principal está em `src/jacare_analytics/pipeline.py`. Cada geração guarda hashes de fonte, contagens de linhas descartadas, cobertura de telefone pseudonimizado, indicadores de campos ausentes, recortes temporais e os totais esperados. O dbt executa modelos e testes; a auditoria compara pedidos e valor recebido com a planilha original por uma leitura independente.

Datas sem registros ficam nulas nos alvos e não viram exemplos de venda zero no ML. Os indicadores de cobertura reais ficam no ambiente privado.

O Meta Ads atual é harmonizado selecionando um único relatório e apenas as linhas diárias no nível de anúncio. Linhas totais e resumos de campanha/conjunto/anúncio são excluídos. A soma do gasto diário é reconciliada contra o total geral antes de publicar a geração.
