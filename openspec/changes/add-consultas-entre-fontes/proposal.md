# Proposal

## Why

Cada consulta da Maria acessa uma só fonte. Para relacionar fomento e Simcc, o modelo consulta uma fonte, copia até 100 Lattes para o SQL e filtra a outra. Isso impede agregações sobre grupos maiores ("artigos de todos os 3.653 bolsistas de doutorado"), gasta de 30 a 68 mil tokens por pergunta, contra ~19 mil numa de fonte única, e deixa para o modelo dizer quantos bolsistas foram encontrados, a falha mais recorrente do `task eval`. Em produção, só 1.230 de 32.798 Lattes do fomento estão no Simcc, então omitir a cobertura levaria a números enganosos. As decisões de arquitetura estão na issue #4.

## What Changes

- **Consulta entre fontes:** nova ferramenta `query_across_sources`, com SQL que cita tabelas como `fonte.schema.tabela`. Executa em DuckDB em memória, criado por consulta, com as origens anexadas em modo somente leitura. `query_data` continua igual para uma fonte só.
- **Ligações entre fontes no catálogo:** novo dado editorial que declara quais colunas ligam duas fontes. O primeiro é `fomento.public.pesquisadores.lattes` ↔ `simcc.public.researcher.lattes_id`. Tem API, seed em `catalog/concepts.yaml`, exportação e tela na demo.
- **Junção só por ligação declarada:** o validador recusa junções entre fontes por colunas sem ligação ativa. Isso preserva a política dos conceitos, por exemplo a de não cruzar instituições por nome.
- **Mesmas regras de sempre:** entidades e colunas permitidas, funções da lista, colunas `aggregate`, `MATCH_TEXT`, limite de linhas, sanitização e quarentena dos resultados valem também entre fontes.
- **Cobertura automática:** quando a consulta usa uma ligação, a ferramenta devolve quantas chaves o lado de origem tem e quantas foram encontradas no outro. A regra do prompt obriga o modelo a informar esses números.
- **Salvaguardas de execução:**
  - acesso externo desligado e configuração travada depois do `ATTACH`;
  - limites de memória e de threads, e de consultas simultâneas;
  - `statement_timeout` e `default_transaction_read_only` na conexão com cada origem;
  - interrupção no tempo limite;
  - URLs fora de mensagens de erro.
- **Instruções:** sai das fontes a orientação de passar até 100 Lattes por consulta.
- **Imagem:** a extensão `postgres` do DuckDB é instalada no build, sem download em execução.
- **Gabarito:** perguntas entre fontes passam a esperar a agregação real, e a conferência aceita etapas entre fontes.
- **Demo:** lista e edição de ligações. O andamento mostra as fontes da consulta.

### Fora do escopo

- Correspondência de instituições entre fontes (#2).
- Índice de entidades e `describe_entities` (segunda etapa da #3).
- Ligações entre mais de duas fontes numa mesma consulta: cada consulta usa no máximo duas.
- Limite de custo prévio por `EXPLAIN` entre fontes: a proteção é o `statement_timeout` em cada origem, somado aos limites do DuckDB.
- Levar esta mudança ao servidor: o deploy é um pedido à parte. A verificação contra produção é só de leitura.

## Capabilities

### New Capabilities

Nenhuma.

### Modified Capabilities

- `data-querying`: consulta entre fontes, validação com vários catálogos, junção por ligação declarada, cobertura e salvaguardas de execução.
- `data-catalog`: ligações entre fontes (modelo, API, seed, exportação e contexto) e instruções sem o limite de 100 Lattes.
- `conversation-messaging`: ferramenta entre fontes no agente e evento de atividade com várias fontes.
- `demo-page`: ligações entre fontes na aba do catálogo.

## Impact

- **Código:**
  - novo `query/federation.py` (execução no DuckDB);
  - `query/validator.py` e `query/match_text.py` (vários catálogos e dialeto `duckdb`);
  - `query/tool.py` e `services/chat.py` (ferramenta e atividade);
  - `models.py`, `schemas.py`, `routers/catalog.py`, `catalog/yaml_io.py`, `catalog/context.py` (ligações);
  - `demo/catalog.js` e `demo/index.html`;
  - `evaluation/` (fontes e conferência entre fontes).
- **Dependências:** `duckdb` no `pyproject.toml` e a extensão `postgres` no `Dockerfile`; a extensão `sqlite` entra só para os testes.
- **Banco da Maria:** migração que cria `catalog_source_links`. Nenhum dado existente muda.
- **Bancos externos:** somente leitura, com os papéis `maria_leitura` existentes. Nada é criado nas origens. As consultas entre fontes podem ler mais linhas por chamada do que as de hoje; o design trata essa carga.
- **Segredos:** as URLs passam a ser usadas em memória no `ATTACH` e nunca são gravadas nem aparecem em erros.
- **Endpoints sem autenticação:** as novas rotas `/catalog/links` nascem sem autenticação, como o resto do catálogo, enquanto o observatorio-idp não estiver pronto.
- **Configuração:** `QUERY_FEDERATED_MEMORY_LIMIT`, `QUERY_FEDERATED_THREADS` e `QUERY_FEDERATED_MAX_CONCURRENT` vão para o `.env.example` e para a tabela de configuração do README.
- **LGPD:** o cruzamento identifica bolsistas pelo nome do Simcc em escala. O acesso `full` já foi decidido pelo usuário; colunas `aggregate` continuam protegidas.
- **Dependências entre mudanças:** nenhuma em andamento. A segunda etapa da #3 vem depois desta.
