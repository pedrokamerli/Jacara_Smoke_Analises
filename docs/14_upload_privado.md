# Atualização de dados pelo dashboard privado

## Para o responsável pela hamburgueria

Entre no endereço privado com uma das contas Google já autorizadas. Tanto o
responsável pelo projeto quanto o proprietário podem enviar arquivos. Não há upload
no site público e não são criadas novas permissões para outras contas.

1. No menu lateral, escolha **Atualizar dados**.
2. Envie o ZIP oficial atualizado ou selecione os arquivos XLSX/CSV de uma vez.
3. Informe a última data realmente completa. Para setembro completo: **30/09/2026**.
4. Confirme que o pacote contém o histórico consolidado.
5. Clique em **Enviar e processar atualização** e acompanhe as etapas.
6. Quando aparecer **Concluída**, volte às análises ou recarregue o painel.

O processo continua se o navegador for fechado. A tela consulta o andamento a cada
cinco segundos. Se o worker estiver indisponível, o envio é recusado; não fica
parecendo uma atualização aprovada. Só um pacote é processado por vez.

### O que deve estar no ZIP

Esta versão recebe **um pacote cumulativo**, não faz mesclagem automática de lotes
mensais. Para atualizar setembro sem perder janeiro–agosto, exporte o histórico do
início até setembro nos mesmos layouts oficiais usados na primeira importação.
Arquivos de plataformas externas podem ter coberturas diferentes: isso continua
explícito no dashboard e não autoriza somar relatórios sobrepostos.

| Fonte | Arquivo esperado |
| --- | --- |
| Pedidos PDV | `01_Todos_os_pedidos_...xlsx` |
| Itens vendidos | `02_Historico_Itens_Vendidos_...xlsx` |
| AppDelivery/MenuDino | `Pedidos_AppDelivery_...xlsx` |
| 99Food | `_Dados do pedido(...).xlsx` |
| Instagram | Seis CSVs oficiais: alcance, visualizações, interações, visitas, cliques e seguidores; nomes mantêm o identificador Instagram e da métrica |
| Meta Ads | `04_Relatorio_Meta_Atualizado_ate_...xlsx`, opcional |
| iFood adicional | `01_Analise_Jacare_Tratada.xlsx`, opcional |

As datas dos nomes podem mudar; as colunas, abas e significados continuam sujeitos
aos contratos dos leitores. Um ZIP qualquer ou um relatório com outro layout não é
automaticamente compatível. A tela informa fontes obrigatórias ausentes. Duas versões
conflitantes da mesma fonte são recusadas; duplicatas idênticas não são somadas.

As fontes opcionais não enviadas ficam ausentes na nova geração. Não reaproveitamos
silenciosamente um relatório antigo como se tivesse sido atualizado.

## Etapas técnicas

O Streamlit revalida a identidade Google e a política de autorização ao receber o
envio. A fila recebe arquivos com nomes internos gerados pelo sistema, integridade
SHA-256 e identificação pseudonimizada do autor, sem registrar seu e-mail em logs.

O worker separado e sem acesso à rede realiza:

1. Validação do pacote, integridade e limites.
2. Preparação, remoção de identificadores diretos e pseudonimização com o HMAC estável.
3. Construção e testes SQL/dbt em um workspace exclusivo.
4. Reconciliação com os totais de origem e validação da allowlist de colunas.
5. Geração das 15 respostas e avaliação temporal dos candidatos de ML e baselines.
6. Materialização do banco portátil, sem referências a arquivos transitórios.
7. Conferência de que o pacote não reduz as bordas nem a contagem de pedidos pagos
   do histórico anterior; reduções deliberadas/correções exigem revisão técnica.
8. Preservação da previsão anterior e troca atômica do manifesto ativo.

Leitores existentes podem terminar usando o snapshot antigo, que continua disponível.
As próximas consultas usam o novo identificador de geração, inclusive no cache.
Falhas antes da publicação mantêm o manifesto anterior intacto. Interrupções e limite
de tempo são tratados como falha, ou recuperados como concluídos se a troca atômica
já ocorreu. Não há treinamento dentro do processo de atendimento do dashboard.

## Previsão original versus realizado

Antes de atualizar, o worker arquiva as métricas originais da geração ativa em
`data/forecast_archive`, sem sobrescrever uma previsão já preservada. Os novos
modelos podem prever outro mês, mas não alteram a estimativa antiga de setembro.

A página de ML permite escolher a origem preservada e comparar com os dados reais
da geração atual. Comparações exigem pelo menos sete dias observados elegíveis;
dias ausentes ou com menos de cinco pedidos não são inventados nem comparados.
Totais e erro absoluto médio usam os mesmos dias comparáveis, não garantem cobertura
do mês inteiro. A avaliação retrospectiva não aprova automaticamente o modelo para
uso operacional.

## Segurança e limites operacionais

- Público: demo sintética inalterada, sem fila ou volume real.
- Dashboard privado: banco e credenciais em mounts somente leitura; apenas a fila
  é gravável. Nenhum navegador de pastas do servidor fica disponível.
- Worker: sem rede, sem credenciais Google, raiz somente leitura e limite de 2 GiB,
  uma CPU e 128 processos. O HMAC fica em mount próprio somente leitura.
- Arquivos: até 200 MiB enviados; fontes selecionadas até 100 MiB, limites para ZIPs
  aninhados e descompressão. XLSX falsos ou com macros são recusados, assim como
  traversal e links nos ZIPs. Não são executadas macros, scripts ou conteúdo enviado.
- Originais e workspaces são transitórios e removidos ao encerrar o trabalho. Os
  snapshots aprovados, previsões e status são privados e permanecem para auditoria.
- Nginx: apenas o vhost privado recebe limite de upload maior; outros projetos são
  preservados. A configuração anterior e o Compose anterior têm cópias de retorno.
- Limite de processamento: 30 minutos. O envio também exige espaço livre e worker
  com heartbeat recente. Não há antivírus integrado nem promessa de segurança absoluta;
  a origem deve continuar sendo um relatório oficial enviado por conta autorizada.

Segredos, arquivos reais, fila, capturas e saídas de QA não devem entrar no Git. O
contexto de build é montado por allowlist de código/SQL, sem originais nem chaves.
Backups externos criptografados e política de retenção dos snapshots devem ser
configurados conforme a operação da VPS; não são substituídos pelo rollback local.

Referências de implementação: [upload seguro da OWASP](https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html)
e [atualização periódica por fragments do Streamlit](https://docs.streamlit.io/develop/api-reference/execution-flow/st.fragment).
