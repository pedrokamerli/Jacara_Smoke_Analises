# CRISP-DM e decisões do projeto

## 1. Entendimento do negócio

O projeto apoia acompanhamento de vendas, planejamento da operação, investigação do cardápio, recorrência e marketing da Jacaré Smoke House, em Bauru/SP. As 15 perguntas do README definem o escopo.

Definições iniciais:

- Pedido pago: status `Finalizado - Pago` no PDV, normalizado para `paid`.
- Data de venda: data de abertura informada no arquivo.
- Valor recebido: soma de `Total Recebido` nos pedidos pagos.
- Ticket recebido: valor recebido dividido por pedidos pagos.
- Recorrência: pelo menos dois pedidos pagos com a mesma chave HMAC no intervalo analisado.
- Canal: origem do pedido na fonte, preservando o significado de cada sistema.
- Semana: segunda a domingo; rankings exigem sete datas contidas no intervalo.
- Funcionamento atual informado: terça a domingo, das 18h30 às 23h, fuso de São Paulo. Exceções históricas continuam pendentes; registros e lacunas não são corrigidos por suposição.

Não há custos completos para inferir lucro ou rentabilidade. A origem Desktop não define, sozinha, modalidade de atendimento. A primeira observação de um cliente no histórico não define sua primeira compra na vida.

## 2. Entendimento dos dados

Evidências: inventário de cabeçalhos, perfil de pedidos e itens, hashes das fontes e manifesto de cada geração. Snapshots sobrepostos são mantidos como referência, não concatenados. Fontes secundárias com dados pessoais em abas vizinhas só são lidas pelo parser específico da aba autorizada.

## 3. Preparação

Evidências: Parquet em `data/runs/<geração>/processed/` e `source_manifest.json`. Os parsers usam campos explicitamente selecionados. Telefones são transformados em memória por HMAC; nomes, endereços e texto livre são descartados. Datas sem registro mantêm alvo ausente.

## 4. Modelagem

Evidências: staging e marts SQL/dbt, consultas `sql/business/` e quatro algoritmos locais (Random Forest, Extra Trees, Hist Gradient Boosting e Ridge), comparados com duas referências. Escolha em seis janelas, congelada antes de duas semanas finais. Recorrência e ciclo de vida são agregados, sem exportação de chaves individuais na apresentação.

## 5. Avaliação

Evidências: `dbt/run_results.json`, `quality_report.json`, relatório das 15 perguntas, métricas de ML e resultados por janela. O pipeline só publica uma geração após construir, testar e reconciliar as tabelas. Modelos não são aprovados somente porque foram treinados.

## 6. Implantação

Evidências: dashboard local, importação por arquivos/ZIP/pasta e CLI compartilhada. O manifesto aponta para uma geração isolada. Falha durante atualização não troca o conjunto ativo. Docker/Compose preparam uma demo independente e somente leitura; resultados reais não são exportados publicamente. O controle Google antecede a leitura privada, mas cliente OAuth e fluxo real ainda precisam de configuração e homologação. Não foi realizado deploy.

## Validações de negócio pendentes

| Tema | Tratamento implementado | Validação com a operação |
|---|---|---|
| Datas sem registro | Nulos, excluídos do treino e da pontuação como alvos | Distinguir fechamento da loja de lacuna de captura |
| AppDelivery × MenuDino | Comparação diária, sem somar fontes | Confirmar se são exportações dos mesmos pedidos |
| iFood_App × PDV | Recorte separado e comparação diária | Identidade e abrangência dos pedidos, sem ID na aba |
| Instagram | Valores exportados preservados, sem somar | Definição de cada série: fluxo ou estoque/acumulado |
| Meta Ads | Detalhamento diário reconciliado com total | Atribuição e objetivo dos resultados para análise de conversão |
| Receita e custos | Valor recebido e deduções da plataforma separados | Conceitos contábeis e custos para eventual análise de lucro |

Essas pendências limitam a interpretação operacional; não são preenchidas com suposições ou dados inventados.
