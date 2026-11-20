# Adicionar grupos do ODA para o recorte SIMCC

## What Changes
- Adicionar o PostgreSQL somente leitura do ODA como fonte da Maria.
- Disponibilizar grupos, instituição sede, pesquisadores, linhas de pesquisa e setores de aplicação.
- Impor na validação SQL que somente grupos com instituição `SEDE` do SIMCC e seus dados relacionados sejam consultados.

## Why
A Maria precisa responder perguntas sobre os grupos SIMCC usando os dados já coletados pelo ODA, sem replicar esses dados nem ampliar o acesso para grupos de outras instituições.

## Impact
- Adiciona `ODA_DATABASE_URL` e a rede Docker externa `maria_IA`.
- O banco externo do ODA permanece somente leitura; nenhuma tabela, view, role ou dado será alterado.
- A fonte e as consultas seguem a política de acesso existente da API; não adiciona autenticação.

## Fora do escopo
- Sincronizar dados do ODA para o banco da Maria.
- Consultar grupos em que a instituição SIMCC seja apenas parceira.
- Expor produções, contatos ou outras tabelas ODA.
