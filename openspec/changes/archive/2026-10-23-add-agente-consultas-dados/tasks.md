# Tasks

## 1. Colunas pesquisáveis no catálogo

- [x] 1.1 Adicionar `searchable` em `CatalogColumn` com migração Alembic (`server_default=sa.false()`, nome em ASCII) e verificar `alembic upgrade head`, `downgrade -1` e `upgrade head` sem erro
- [x] 1.2 Expor `searchable` no detalhe e no PATCH de coluna (rejeitando `null`), preservá-lo na sincronização e criar colunas novas não pesquisáveis; verificar com testes de API e de sincronização
- [x] 1.3 Ler e escrever `searchable` no seed e na exportação YAML e marcar no `catalog/fomento.yaml` `projetos.nome`, `projetos.resumo`, `palavras_chave.termo` e `areas_conhecimento.termo`; verificar com o teste de ida e volta do YAML
- [x] 1.4 Indicar "aceita busca textual" na linha da coluna em `render_context`; verificar com teste da prévia, incluindo coluna oculta e pesquisável fora do contexto
- [x] 1.5 Adicionar o interruptor pesquisável na aba do catálogo da demo e documentar o campo no README (seção do catálogo); verificar no navegador que ligar o interruptor altera a prévia

## 2. Validação de consultas

- [x] 2.1 Adicionar `sqlglot` às dependências e criar o pacote `query/` com o schema de validação montado a partir do catálogo (só itens visíveis e presentes); verificar com `poetry install` e um teste que monta o schema do seed do fomento
- [x] 2.2 Implementar as recusas de instrução única `SELECT`/`WITH`, entidades ocultas, ausentes, inexistentes e não consultáveis, colunas ocultas e asteriscos, com mensagens que não revelam itens ocultos; verificar com testes por cenário da spec `data-querying`
- [x] 2.3 Implementar a lista de funções permitidas e a regra das colunas `aggregate` (permitidas fora do `SELECT` e dentro de agregações, inclusive em CTEs e subconsultas); verificar com testes de `pg_sleep`, `COUNT(DISTINCT cep_referencia)` aceito e `SELECT cep_referencia ... GROUP BY` recusado
- [x] 2.4 Implementar a reescrita de `MATCH_TEXT` (normalização de acentos e caixa, vários termos, escape de `%`/`_`, recusa de termos vazios e de colunas não pesquisáveis) para PostgreSQL e SQLite; verificar com testes do SQL gerado nos dois dialetos

## 3. Execução somente leitura

- [x] 3.1 Implementar a execução numa transação somente leitura, com limite de tempo e de linhas (`QUERY_MAX_ROWS`, `QUERY_TIMEOUT_SECONDS`), detecção de truncamento e conversão de valores para JSON; verificar com testes de integração numa origem SQLite temporária em arquivo, incluindo truncamento, tempo esgotado e origem inacessível sem URL na mensagem
- [x] 3.2 Implementar o `ResultStore` por resposta e a ferramenta `query_data` (validação, execução, `result_id`, recusas como resultado, `QUERY_MAX_PER_CALL`); verificar com testes da ferramenta, incluindo excesso de consultas numa chamada
- [x] 3.3 Verificar `MATCH_TEXT` contra a origem SQLite com resumos acentuados ("Dengue", "ARBOVIROSES", "Saúde") e documentar no README as variáveis `QUERY_*`, também incluídas no `.env.example`

## 4. Laço do agente no chat

- [x] 4.1 Criar o fake de modelo de teste com `bind_tools` e `tool_calls` roteirizados e verificar que ele reproduz uma sequência consulta → resposta num teste do serviço
- [x] 4.2 Montar o novo prompt (instruções da Maria, regras das ferramentas, data atual em `America/Bahia`, contexto das fontes consultáveis) e resumir blocos `chart`/`table` do histórico; verificar com os cenários do requisito "Contexto da conversa"
- [x] 4.3 Implementar o laço em `stream_message` com `MARIA_AGENT_MAX_MODEL_CALLS` (padrão 3, `ge=1`), "chamadas restantes" nos resultados e a última chamada sem `query_data`; verificar com testes de orçamento esgotado, de resposta sem fontes em uma chamada e de valor 0 recusado na inicialização
- [x] 4.4 Implementar `show_chart` e `show_table` preenchidos pelo servidor (tipos inferidos do resultado, recusa de colunas inexistentes) e a ordem dos blocos (texto, depois gráficos e tabelas); verificar com os cenários de gráfico por ano e lista de projetos
- [x] 4.5 Adicionar o evento `activity` e os `content.delta` com `block` para `chart`/`table` em `schemas.py` e no router de streaming, mantendo persistência atômica, erro e interrupção como antes; verificar com testes de SSE, incluindo a ordem `message.user` → `activity` → `content.delta` → `message.assistant`
- [x] 4.6 Verificar com o fake o cenário da resposta parcial (fomento sobre dengue respondido, artigos declarados indisponíveis) e documentar no README o fluxo de consultas, o orçamento e a variável no `.env.example`

## 5. Observabilidade das consultas

- [x] 5.1 Gerar spans de ferramenta OpenInference para `query_data` (fonte, SQL, linhas, truncamento ou motivo da recusa), respeitando a ocultação de conteúdo; verificar com testes de span com e sem ocultação
- [x] 5.2 Registrar `maria.agent.model_calls` e `maria.query.count` (`outcome`, fonte); verificar com testes de métricas e incluir os dois painéis no dashboard "Maria · API e IA" do Grafana

## 6. Demo

- [x] 6.1 Exibir as descrições de `activity` na mensagem do assistente e renderizar `chart`/`table` das respostas no streaming e no histórico, reaproveitando os renderizadores da aba de contrato; verificar no navegador com o fake ou com o fomento
- [x] 6.2 Verificar a demo no navegador em desktop e a 375px: andamento das consultas, gráfico e tabela sem rolagem horizontal da página e interruptor pesquisável na aba do catálogo

## 7. Verificação contra o sistema real

- [x] 7.1 Com o fomento real e o modelo configurado, perguntar "Existe fomento na temática de dengue entre 2024 e 2026? Quais projetos e que artigos foram produzidos?" e verificar no Phoenix: no máximo 3 chamadas, consultas com `MATCH_TEXT` em título, resumo e palavras-chave, gráfico e tabela com números iguais aos do banco e artigos declarados indisponíveis
- [x] 7.2 Desfazer qualquer edição de teste no catálogo e rodar `task test` (lint, testes e cobertura) sem falhas

## Workflow follow-up

- Arquivar a mudança após a revisão, seguindo os commits definidos no `config.yaml`.
- Abrir a mudança do Simcc (pesquisadores, titulação e artigos) reaproveitando `query_data` e reavaliando o orçamento padrão.
