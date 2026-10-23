# Proposal

## Why

Hoje a Maria responde só com o que o modelo já sabe: o catálogo de dados existe, mas não chega ao modelo, e ela não consulta nenhum banco nem monta gráficos ou tabelas. Perguntas como "existe fomento na temática de dengue entre 2024 e 2026? Quais projetos?" exigem cruzar período, tema em texto livre (título, resumo e palavras-chave) e agregações, e precisam ser respondidas com números reais do fomento, num custo previsível por resposta.

## What Changes

- **A Maria passa a consultar as fontes do catálogo.** As fontes ativas com entidades consultáveis entram no prompt (o mesmo texto da prévia de contexto), e o modelo ganha ferramentas para consultar cada fonte em SQL somente leitura.
- **Consultas validadas pelo catálogo antes de executar:** só `SELECT` (com `WITH`), uma instrução por vez, apenas entidades visíveis, consultáveis e presentes, apenas colunas visíveis, colunas de "somente agregação" nunca projetadas, funções numa lista permitida, limite de linhas e de tempo. A consulta recusada volta ao modelo com o motivo, para ele corrigir.
- **Busca textual léxica:** uma função de busca usada dentro do SQL (`MATCH_TEXT`) que ignora acentos e maiúsculas e aceita vários termos, para o modelo expandir o tema com sinônimos (ex.: dengue, Aedes aegypti, arbovirose). Só vale em colunas marcadas como **pesquisáveis** no catálogo.
- **Catálogo:** novo interruptor editorial **pesquisável** por coluna, na API, no YAML, na prévia de contexto e na demo. O seed do fomento marca título e resumo dos projetos e os termos de palavras-chave e áreas.
- **Gráficos e tabelas a partir dos resultados:** o modelo pede um gráfico ou tabela apontando para o resultado de uma consulta e escolhendo tipo e colunas; o servidor preenche os dados com as linhas reais. O modelo nunca digita os números dos blocos.
- **Orçamento de chamadas ao modelo por resposta:** no máximo `MARIA_AGENT_MAX_MODEL_CALLS` (padrão 3), contando a resposta final. A última chamada é sempre sem ferramentas de consulta, então sempre há resposta. O modelo sabe quantas chamadas restam e pode fazer várias consultas na mesma chamada. Não há etapa de plano separada.
- **Resposta parcial honesta:** quando parte da pergunta depende de dados que nenhuma fonte ativa tem (ex.: artigos e titulação, que virão do Simcc), a Maria responde o que conseguiu e diz o que não pôde responder e por quê.
- **Data atual no prompt**, para o modelo interpretar períodos como "até hoje" ou "2024 a 2026".
- **Streaming:** novo evento `activity` com uma descrição curta do que a Maria está consultando, e blocos `chart`/`table` entregues inteiros em `content.delta`.
- **Observabilidade:** cada consulta vira um span de ferramenta filho de `maria.chat`, com métricas de chamadas ao modelo e de consultas executadas e recusadas.
- **Demo:** mostra o andamento das consultas e renderiza gráficos e tabelas das respostas reais. A aba do catálogo ganha o interruptor pesquisável.

### Fora do escopo

- Integração do Simcc (pesquisadores, titulação e artigos). Esta mudança só deixa o caminho pronto: várias fontes no mesmo prompt e o Lattes registrado como chave de ligação futura.
- Filtrar pesquisadores por titulação ("doutores"): os dados não estão no fomento hoje.
- Busca semântica (embeddings), inclusive com os `search_document` do Simcc.
- Junção entre bancos diferentes numa mesma consulta.
- Triagem prévia com o nível `fast`, consultas nomeadas e cache de resultados.
- Orçamento por tokens ou por usuário (o orçamento é por resposta, em chamadas).
- Autenticação.

## Capabilities

### New Capabilities

- `data-querying`: consulta da Maria às fontes do catálogo: validação das consultas contra o catálogo, execução somente leitura com limites, busca textual léxica e os resultados que alimentam gráficos e tabelas.

### Modified Capabilities

- `conversation-messaging`: o contexto da resposta passa a incluir as fontes consultáveis e a data atual. As respostas podem trazer blocos `chart` e `table` vindos de consultas, com orçamento de chamadas, resposta parcial e o novo evento `activity` no streaming.
- `data-catalog`: novo interruptor **pesquisável** por coluna, refletido na API, no YAML e na prévia de contexto.
- `observability`: spans de ferramenta para as consultas e métricas de chamadas e consultas por resposta.
- `demo-page`: andamento das consultas, gráficos e tabelas reais nas respostas e o interruptor pesquisável na aba do catálogo.

## Impact

- **Bancos externos:** a Maria passa a **ler dados** (não só o schema) do banco do fomento, sempre em transação somente leitura, com limite de tempo e de linhas. Nada é criado, alterado ou removido na origem. Recomenda-se um usuário de banco só de leitura em `FOMENTO_DATABASE_URL`.
- **Segredos:** nenhum segredo novo. As URLs de conexão continuam fora do banco, da API, dos prompts e das mensagens de erro.
- **Endpoints sem autenticação:** nenhum endpoint novo. A edição de coluna em `/catalog` ganha o campo `searchable`, e qualquer cliente da API passa a disparar consultas ao fomento pelo chat. Os dois continuam sem autenticação até o observatorio-idp ficar pronto.
- **Código:** `services/chat.py` (laço do agente), novo pacote `query/` (validação, execução, busca textual, resultados), `llm/prompts.py`, `catalog/context.py`, `models.py`, `schemas.py`, `routers/catalog.py`, `observability/genai.py`, demo.
- **Banco da Maria:** coluna `searchable` em `catalog_columns` (migração Alembic).
- **Dependências:** `sqlglot` (análise e reescrita do SQL).
- **Configuração:** `MARIA_AGENT_MAX_MODEL_CALLS`, `QUERY_MAX_ROWS`, `QUERY_TIMEOUT_SECONDS` e `QUERY_MAX_PER_CALL` no `.env.example`.
- **Custo:** até 3 chamadas ao modelo por resposta (antes era 1).
- **Dependências entre mudanças:** nenhuma em andamento. Todas as anteriores estão arquivadas.
