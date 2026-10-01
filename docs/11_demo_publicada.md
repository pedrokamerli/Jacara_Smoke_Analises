# Registro de publicação - 01/10/2026

Demo disponível em https://analisejacare.pedromerli.com, com HTTPS e redirecionamento HTTP. Somente dados sintéticos; o ambiente real não foi publicado.

## Implantação

- Projeto Compose independente: jacare-demo; contêiner jacare_demo.
- Diretório da release: /opt/portfolio/jacare-analytics/releases/20261001T114846Z.
- Rede existente evolync_network; nenhuma porta de aplicação vinculada à interface pública.
- Usuário 10001, filesystem somente leitura, capacidades removidas, memória/CPU limitadas, sem volumes ou credenciais.
- Pacote por allowlist, SHA-256 49d6cfb6c9b3a070bde5d1252c791ed359eef2ceb22eae3d360e786e6971a15f.
- Apenas código/configuração e quatro arquivos públicos sintéticos. Nenhum arquivo real, modelo, HMAC ou segredo Google foi transferido.
- Nginx ganhou somente o bloco BEGIN/END JACARE DEMO MANAGED. Backups preservados antes das alterações. Atualização validada antes de reload, sem reiniciar o proxy.
- Certificado emitido via Certbot com renovação agendada e hook já existente de reload do Nginx.

## Evidências

Health do serviço por HTTPS retornou ok; página principal retornou 200 e HTTP retornou 301. As oito telas passaram via AppTest dentro da imagem implantada. A navegação real confirmou a identificação de demonstração e o gráfico mensal. Não há upload público nem acesso ao banco privado.

As outras duas análises verificadas continuam respondendo. Não foram executados comandos de alteração ou reinício sobre esses projetos. A inspeção encontrou mudança de identidade no contêiner de outra análise durante o intervalo, sem comando nosso sobre ele; não se afirma que o estado de todos os serviços da VPS permaneceu idêntico.

A primeira tentativa HTTPS foi recusada por diretivas duplicadas e sofreu rollback automático. O helper foi corrigido para reutilizar proxy_params sem duplicar diretivas; nginx -t passou depois da correção. O primeiro teste de certificado imediatamente após reload ocorreu antes de os novos workers assumirem; a nova verificação com validação TLS normal passou, sem bypass de certificado.

## Atualização e recuperação

Gerar nova release local por scripts/package_demo.py, revisar, transferir e conferir checksum. Nunca copiar a raiz do projeto nem usar o diretório de dados reais como contexto de build. Antes de trocar o serviço, preservar imagem/Compose anteriores e testar a nova imagem. Evitar reconstruir todos os projetos da VPS.

O bloco foi adicionado ao arquivo runtime existente do Nginx. Scripts externos que regenerem esse arquivo podem removê-lo; registrar o domínio no processo central de geração antes de usar tal automação. Restaurar backup só com revisão das alterações posteriores: não sobrescrever configurações de terceiros indiscriminadamente.

Esta publicação não equivale a auditoria de segurança completa. Dependências e digest da imagem devem ser fixados em uma release reproduzível após revisão, e a imagem precisa de análise de vulnerabilidades contínua. Nenhum commit ou push foi realizado.

## Google e área real

Credenciais importadas somente para .streamlit/secrets.toml local, com permissões restritas, e callback de produção validado. Nenhum segredo foi exibido ou incluído na release. allowed_emails permanece vazio; acesso real bloqueado. Falta autorização das contas, implantação privada separada e homologação do login antes de disponibilizar dados reais.
