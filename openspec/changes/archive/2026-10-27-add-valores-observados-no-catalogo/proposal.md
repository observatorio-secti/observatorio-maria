# Proposal

## Why

A pergunta "Quantas bolsas de doutorado entre 2016 e 2026?" gerou `WHERE modalidade = 'Doutorado'` e voltou `NULL`. No banco do fomento, os valores reais são `Doutorado - Cotas`, `Iniciação Científica - Cotas`, `Mestrado - Cotas` e `Mestrado Profissional - Cotas`. O modelo seguiu o catálogo, e o catálogo estava errado. Hoje só colunas com enum nativo do PostgreSQL têm valores lidos da origem. Nas colunas de texto, o modelo depende de valores escritos à mão no YAML: em `bolsas.modalidade` eles foram escritos por suposição, e `mv_bolsas_metricas.modalidade` não tem nenhum. Os exemplos few-shot também não são checados contra o catálogo (um deles usa `ano`, que não existe na view). E um resultado vazio não leva o agente a desconfiar do filtro.

## What Changes

- **Valores observados em colunas categóricas de texto:** a sincronização e a verificação periódica leem os valores distintos das colunas de texto visíveis, de entidades consultáveis e com acesso `full`. Se uma coluna tem até `CATALOG_OBSERVED_VALUES_MAX` valores distintos (padrão 50), eles são guardados num campo técnico (`observed_values`). Acima disso, a coluna é tratada como texto livre e o campo fica nulo. Os valores observados não entram na impressão digital do schema: mudança nos dados não é defasagem.
- **Valores observados no contexto do modelo:** quando a coluna não tem enum, a lista de valores conhecidos passa a ser a dos valores observados, com as descrições editoriais que houver. Um valor editorial que não aparece na origem fica obsoleto e sai do contexto, como já acontece com enums. Isso corrige `bolsas.modalidade` no banco já semeado, sem edição manual.
- **API e demo:** a coluna expõe `observed_values`. Valores sem descrição e obsoletos passam a valer também para colunas com valores observados. A demo mostra a origem dos valores ("lidos da origem").
- **Exemplos few-shot conferidos com o catálogo:** cada exemplo passa pela mesma validação do `query_data` (entidades, colunas e funções permitidas). Exemplos inválidos ficam fora do contexto do modelo, e a prévia do contexto lista cada um com o motivo.
- **Aviso em resultado vazio:** quando `query_data` devolve zero linhas, ou uma única linha só com valores nulos, a resposta traz um `hint`. Ele orienta o modelo a conferir os valores existentes (`SELECT DISTINCT`) antes de concluir que não há dados. O prompt ganha a regra correspondente.
- **Orçamento de chamadas ao modelo:** o padrão de `MARIA_AGENT_MAX_MODEL_CALLS` sobe de 3 para 6, para caber a verificação (consulta → conferir valores → nova consulta → resposta).
- **Seed do fomento corrigido:** remove de `bolsas.modalidade` os valores escritos por suposição (os valores reais virão da origem) e troca `ano` por `ano_inicio` no exemplo de totais por ano.

### Fora do escopo

- Descrever o significado de "Cotas" ou de outras modalidades: é regra de negócio e fica pendente para quem conhece o domínio.
- Valores observados de colunas com acesso `aggregate`, de colunas ocultas e de colunas numéricas ou de data.
- Ferramenta dedicada para listar valores (`list_values`): o modelo já pode usar `SELECT DISTINCT` via `query_data`.
- Conjunto de perguntas de referência rodando contra LLM real: os testes do projeto não chamam LLMs reais, e isso pede uma mudança própria.
- Validar os exemplos com `EXPLAIN` na origem.

## Capabilities

### New Capabilities

Nenhuma.

### Modified Capabilities

- `data-catalog`: valores observados (leitura, guarda, uso no contexto, pendentes e obsoletos) e validação dos exemplos few-shot contra o catálogo.
- `data-querying`: aviso de resultado vazio no retorno de `query_data`.
- `conversation-messaging`: padrão do orçamento de chamadas passa a 6; regra de não concluir ausência de dados sem conferir valores.

## Impact

- **Código:** `catalog/` (novo módulo de leitura de valores, `sync.py`, `drift.py`, `context.py`, `seed.py`), `models.py`, `schemas.py`, `routers/catalog.py`, `query/tool.py`, `llm/prompts.py`, `settings.py`, `demo/catalog.js`, `catalog/fomento.yaml`.
- **Banco da Maria:** migração Alembic que adiciona `catalog_columns.observed_values` (JSON, nulo).
- **Bancos externos:** passam a receber consultas `SELECT DISTINCT ... LIMIT` somente leitura, com timeout, durante a sincronização e a verificação. Nada é escrito na origem. Até aqui a introspecção lia só estrutura; agora ela também lê dados de colunas categóricas visíveis.
- **Configuração:** nova `CATALOG_OBSERVED_VALUES_MAX`; padrão de `MARIA_AGENT_MAX_MODEL_CALLS` muda para 6 (`.env.example` e README). Ambientes cujo `.env` fixa o valor mantêm o valor fixado.
- **Custo:** até o dobro de chamadas ao modelo por resposta no pior caso; o teto de tokens por conversa continua valendo.
- **Segredos:** nenhum novo. **Endpoints sem autenticação:** nenhum novo; os existentes do catálogo ganham campos.
- **Dependências:** nenhuma mudança em andamento.
