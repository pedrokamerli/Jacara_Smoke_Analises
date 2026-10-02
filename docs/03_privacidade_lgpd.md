# Privacidade e proteção de dados

## Regra do projeto

Dados pessoais não entram no Git, no dashboard público, em exemplos, screenshots, logs ou relatórios de portfólio. Isso inclui nomes, telefones, endereços, e-mails, CEP, data de nascimento, IDs de cliente, texto livre de pedidos/avaliações e combinações que permitam identificar alguém.

Os arquivos brutos permanecem localmente e são ignorados pelo `.gitignore`. O fluxo analítico deve selecionar apenas os campos necessários, remover identificadores diretos na preparação e publicar somente indicadores agregados. Não copiar planilhas tratadas existentes sem revisão: algumas podem conter nome e telefone mesmo quando parecem ser material de análise.

Ao executar dbt, prefira definir `DBT_SEND_ANONYMOUS_USAGE_STATS=false`. Isso desativa a telemetria anônima do dbt para a sessão, sem alterar os dados ou modelos locais.

## Recorrência de clientes

Para calcular recorrência, o projeto oferece funções HMAC em `src/jacare_analytics/privacy.py`. Elas permitem substituir telefone ou ID de plataforma por uma chave pseudonimizada, com segredo configurado localmente em `JACARE_ANALYTICS_HMAC_KEY`. Cada fonte recebe um namespace separado; não presumimos que IDs de sistemas diferentes representam a mesma pessoa.

Pseudonimização é uma medida de proteção, mas a chave gerada continua sendo dado pseudonimizado e deve ficar em ambiente local controlado. A chave secreta deve ser forte, estável para reproduzir a análise, guardada fora do repositório e não compartilhada junto com os dados. O arquivo `.env.example` é apenas um lembrete sem segredo real.

No pipeline principal, a função `local_secret` usa a variável configurada ou cria um segredo aleatório estável em `data/private/hmac.key`. O valor não é exibido nem gravado em relatórios. O diretório é ignorado pelo Git. A saída com chaves HMAC permanece dentro da geração privada; consultas de apresentação retornam somente contagens e grupos. O dashboard privado funciona no endereço local configurado; a apresentação pública preparada não recebe o banco privado.

As pastas extraídas conhecidas, `data/runs/` e o manifesto local também estão ignorados. O importador de ZIP não extrai arquivos e só lê membros autorizados. A atualização só ativa resultados após aprovação das verificações; arquivos enviados não são persistidos em formato bruto.

O modo público é somente leitura e exige um pacote separado, revisado e aprovado pelo responsável, com campos agregados explicitamente permitidos. Não recebe pedidos, chaves, Parquet, modelos ou arquivos originais; qualquer arquivo extra no pacote bloqueia a apresentação. Filtros livres de datas e importação ficam indisponíveis. A revisão humana das combinações e da autorização de dados comerciais continua necessária. Detalhes em [publicação segura](09_publicacao_segura.md).

## Minimização e publicação

### Cadastro nominal exclusivamente privado

Por solicitação do responsável pelo projeto, a versão privada autenticada pode
mostrar rankings de clientes por nome, compras e valor recebido. Um artefato
separado liga o nome ao HMAC já usado no warehouse; telefones, e-mails,
endereços, documentos e datas de nascimento não são persistidos nesse cadastro.
Esse artefato é confidencial, continua sendo dado pessoal, não entra no Git,
na imagem Docker, na demo ou nas respostas públicas. Nomes conflitantes para
uma mesma chave são omitidos. Os controles de autenticação são executados
antes de qualquer leitura. As regras de agregação abaixo se aplicam ao público
e às respostas compartilháveis; o ranking privado é uma exceção explícita de
acesso restrito, não uma anonimização nem uma autorização para compartilhá-lo.

- Manter em cada modelo apenas as colunas necessárias para uma pergunta de negócio.
- Excluir identificadores pessoais e observações livres das tabelas analíticas públicas.
- Restringir dados por cliente a um ambiente local e pseudonimizado; no dashboard externo, apresentar apenas grupos e totais agregados.
- Avaliar risco de reidentificação em grupos pequenos; não publicar cortes com poucos clientes nem filtros que revelem uma pessoa.
- Evitar guardar cópias intermediárias contendo identificadores. Quando necessárias para transformação local, limitar acesso e retenção.
- Revisar cada arquivo, imagem e captura antes de qualquer compartilhamento.

Essas práticas são controles técnicos do projeto; não constituem, por si só, uma declaração de conformidade jurídica. A finalidade, a base legal, os acessos e os prazos de retenção devem ser definidos pelo controlador responsável pelos dados.

## Referências oficiais

- [Lei nº 13.709/2018 (LGPD), texto compilado — Presidência da República](https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2018/lei/l13709.htm)
- [Estudo técnico da ANPD sobre anonimização na LGPD](https://www.gov.br/anpd/pt-br/centrais-de-conteudo/documentos-tecnicos-orientativos/estudo_tecnico_sobre_anonimizacao_de_dados_na_lgpd___analise_juridica.pdf/@@download/file)
