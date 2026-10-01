# Login privado - homologação em 01/10/2026

URL: https://jacare.pedromerli.com. Login Google configurado com lista privada de contas. Credenciais foram transferidas por SSH somente ao serviço privado, fora da imagem e do Git. Arquivo com permissões restritas, montado somente leitura.

O erro de aspa na lista local foi corrigido mecanicamente, sem alterar contas/credenciais; original preservado em data/private/config_backups. Não são registrados e-mails ou segredos neste documento.

Serviço jacare_private, Compose próprio em /opt/portfolio/jacare-analytics/private. Rede interna jacare_private_proxy compartilhada apenas com Nginx; rede de saída separada permite conexão ao Google. Sem porta pública direta. Usuário sem privilégios, filesystem somente leitura e recursos limitados. O contexto de build permite somente Dockerfile e os dois arquivos de código atualizados, nunca secrets.toml.

O usuário confirmou login permitido e negação de uma conta não autorizada. Em seguida, foi instalado um snapshot analítico real minimizado em volume somente leitura em `/app/data`, exclusivo do serviço privado. A imagem `jacare-analytics-private:analytics-v1` reutiliza o runtime público, mas não lê a demo no modo privado. A opção de atualizar/importar está desabilitada nesta instância.

Teste anônimo no contêiner aprovado: tela contém somente entrada Google, sem erros, métricas, navegação analítica, downloads ou upload. Google metadata acessível. Certificado emitido, Nginx validado e recarregado com backup; a demo pública mantém serviço próprio.

Correção do erro HTTP 500 no início do login: faltava a dependência HTTP utilizada pela integração Google/Starlette. A imagem privada `login-v2` inclui `httpx`, também declarado nas dependências do projeto. Somente o serviço privado foi reconstruído e recriado. O smoke test agora aciona a rota HTTPS real de autenticação, além de conferir a tela: redirecionamento ao Google aprovado, callback exato `https://jacare.pedromerli.com/oauth2callback`, state e nonce presentes. Tokens, cookies e credenciais não são impressos pelo teste. `pip check` sem dependências quebradas; endpoints de saúde público e privado retornaram `ok` após a correção.

## Snapshot e testes

`scripts/package_private_data.py` conferiu os hashes das fontes oficiais locais contra a proveniência da geração. Essa geração anterior ainda não possuía `dataset_kind`; o novo manifesto privado recebeu `real_confidential` somente após essa conferência. O manifesto local original não foi alterado. As vinte relações analytics foram materializadas em um novo DuckDB: isso remove dependência de caminhos Windows e de Parquet externos. Contagens preservadas e auditoria completa igual à da geração original. Nenhum novo treinamento ou preenchimento fictício foi realizado.

O pacote privado contém somente banco, respostas JSON, narrativa Markdown, métricas/previsões ML, auditoria, proveniência minimizada, manifesto ativo e inventário de hashes. Não contém originais, dados Parquet, arquivos joblib, telefones, nomes de clientes, HMAC ou credenciais. Chaves pseudonimizadas permanecem no banco privado e continuam sendo dados protegidos, não anonimização irreversível.

Arquivo aprovado: `private-20261001T123658Z_4f164ea5.tar.gz`, SHA256 `f1b92915a88708fa31f7a366ea491bcf5fb8a3975975c3cdb1d5a3f8e0d3005e`. Instalador verificou transferência e hashes individuais; arquivos 0400, diretórios do snapshot 0700 e proprietário 10001. O primeiro pacote de staging estava sem o JSON de respostas; o QA detectou a falha antes da ativação, e o pacote completo foi gerado e retestado.

Teste de renderização em contêiner isolado, sem rede: oito telas aprovadas, incluindo perguntas, delivery, marketing, ML e metodologia. Autorização foi simulada exclusivamente no processo desse teste; não há bypass na aplicação publicada. Identidade inválida bloqueada antes de abrir o banco, mesmo com dados presentes. Cinquenta testes locais passaram. Após ativação, sessão anônima continua sem banco, métricas, navegação ou downloads; rota real redireciona ao Google com callback correto.

## Atualização, rollback e limites

Só o serviço privado foi recriado; Nginx foi validado e recarregado para atualizar a resolução do upstream. Imagem e pacote públicos não foram atualizados. Snapshot fica fora da imagem, sob `/opt/portfolio/jacare-analytics/private/datasets/`, com ponteiro privado `data`. Build context continua permitindo exclusivamente os três arquivos definidos, nunca datasets/ ou secrets.toml.

Para nova atualização: processar fontes localmente, concluir auditoria/dbt/ML, executar o empacotador, transferir por SSH, conferir checksum, instalar um novo snapshot e testar antes de recriar o serviço privado. A apresentação na VPS não ingere nem treina. Não copiar raiz do projeto ou fontes originais. Backups contêm dados confidenciais e precisam das mesmas proteções.

Rollback imediato para a tela sem dados: arquivo privado `compose.login-v2.rollback.yaml` conserva a configuração anterior com imagem `login-v2`, sem volume de dados. Reaplicar esse Compose no mesmo projeto `jacare-private` e validar/recarregar Nginx. Snapshots existentes são preservados para recuperação; não executar limpeza ampla de Docker ou volumes.

A confirmação humana de acesso permitido e conta negada não substitui teste de logout, múltiplas abas, expiração, revogação, restauração de backup ou revisão de dependências. A renderização do dashboard com autenticação real após esta atualização ainda deve ser conferida pelo proprietário no navegador. As estimativas usam somente o histórico disponível até agosto; setembro permanece projeção experimental, não resultado realizado nem previsão atualizada de outubro. A implantação não é certificação de segurança/LGPD. Git e Power BI permanecem entregas separadas.
