# Design

## Context

Motivação em `proposal.md`. Estado atual relevante:

- **Fluxo de geração:** `ChatService.stream_message` é o único fluxo de resposta. Recebe sessão, `ModelRegistry`, tracer, callbacks e `AgentMetrics`, e emite `UserMessageCreated`, `Activity`, `ContentDelta` e `AssistantMessageCompleted`. No fim, grava pergunta e resposta e soma os tokens em `conversation.total_tokens`.
- **Consultas:** o `QueryRunner` é criado dentro de `stream_message`. O evento `Activity` traz só o nome da fonte e o propósito, sem o SQL nem o resultado. O `QueryRunner.query_data` valida o SQL (incluindo a macro `MATCH_TEXT`), executa em conexão somente leitura e limita as linhas a `QUERY_MAX_ROWS`.
- **Chamadas ao modelo:** contadas em `stream_message` e enviadas a `AgentMetrics.record_model_calls`.
- **Banco da Maria:** SQLite (`DATABASE_URL`), com o catálogo e as conversas. Comandos de linha (`task seed`) seguem o padrão `argparse` de `catalog/seed.py`.
- **Respostas esperadas da issue #1:** dependem do estado dos bancos de dev (Simcc com 102 pesquisadores).

## Goals / Non-Goals

**Goals:**
- Comparar execuções antes e depois de mudanças no contexto, pergunta a pergunta.
- Medir o comportamento real da API, sem um caminho de geração paralelo.

**Non-Goals:**
- Estatística robusta sobre a variação do modelo: as repetições dão uma noção, não intervalos de confiança.
- Gerar perguntas automaticamente ou avaliar estilo de redação.

## Decisions

### D1. Perguntas em `evals/reference.yaml`, na raiz do repositório
Formato:

```yaml
questions:
  - id: artigos-por-ano
    question: Quantos artigos únicos foram publicados por ano desde 2020?
    tags: [simcc]
    checks:
      - type: sources
        required: [simcc]
        forbidden: [fomento]
      - type: numbers
        values: [16, 19, 17, 13, 18, 29, 22]
    verify:
      - source: simcc
        sql: SELECT year, COUNT(*) FROM public.mv_canonical_articles WHERE year >= 2020 GROUP BY year ORDER BY year
        column: count
```

Tipos de critério: `numbers` (todos os valores devem aparecer), `list` (`items` e `min_ratio`), `sources` (`required` e `forbidden`) e `judge` (`criterion`, texto). O carregamento usa modelos Pydantic e recusa arquivo inválido antes de chamar o modelo.
- *Descartado:* guardar as perguntas no banco da Maria, como o catálogo. São dados de desenvolvimento versionados junto com o código que avaliam, não configuração editada por pessoas pela API.
- *Descartado:* perguntas como testes pytest marcados. Misturaria chamadas reais com a suíte que, por regra, nunca chama LLMs, e o relatório comparativo não cabe no formato de teste.

### D2. Rodar pelo `ChatService` real, numa cópia temporária do banco
O comando copia o arquivo SQLite de `DATABASE_URL` para um diretório temporário, abre uma sessão nele e chama `stream_message` com o registro de modelos real, uma conversa nova por pergunta e repetição. A cópia é apagada no fim.
- *Descartado:* chamar a API HTTP de um servidor rodando. Exigiria o servidor no ar e não daria acesso ao SQL executado.
- *Descartado:* rodar no banco de dev e apagar as conversas depois. Uma interrupção no meio deixaria conversas de avaliação na demo.
- *Descartado:* um banco vazio com o seed. O catálogo de dev tem edições feitas pela demo; a avaliação deve medir o catálogo que a Maria usa de fato.

Se `DATABASE_URL` não for SQLite, o comando termina com erro explicando a limitação: SQLite é o banco da Maria em dev e produção.

### D3. Observador opcional de consultas no `ChatService`
`ChatService` ganha o parâmetro opcional `query_observer`, repassado ao `QueryRunner`. Ele é chamado depois de cada `query_data` com fonte, SQL validado, número de linhas e erro, se houver. A avaliação o usa para o critério `sources` e para o relatório. Na API ele fica `None`, sem efeito.
- *Descartado:* acrescentar o id da fonte e o SQL ao evento `Activity`. O evento vira SSE para o cliente, e o contrato da API não deve expor SQL.
- *Descartado:* ler os spans `query_data` com um exportador em memória. Com `OPENINFERENCE_HIDE_INPUTS=true` o SQL some, e a avaliação ficaria presa à observabilidade.

Tokens vêm de `conversation.total_tokens` depois da resposta. As chamadas ao modelo vêm de um `AgentMetrics` próprio da avaliação, que guarda o último valor registrado.

### D4. Critérios determinísticos sobre o texto e as tabelas
A resposta é a lista de blocos de `AssistantMessageCompleted`. O texto avaliado junta os blocos `text` e as células dos blocos `table` e as séries dos `chart`.
- `numbers`: extrai os números do texto aceitando "3.653", "3653" e "1.234,5", normaliza para `Decimal` e compara.
- `list`: normaliza (minúsculas, sem acentos, espaços colapsados) e procura cada item como substring.
- `sources`: conjunto das fontes das consultas sem erro, vindo do observador (D3).

- *Descartado:* pedir ao juiz para checar números e listas. Seria mais lento, mais caro e não determinístico onde não precisa.

### D5. Juiz com o nível `advanced` do `ModelRegistry`
O critério `judge` chama o modelo do nível `advanced` com saída estruturada (`with_structured_output`) contendo `passed` e `reason`. O prompt do juiz recebe a pergunta, o texto da resposta e o critério, e é instruído a julgar só o critério.
- *Descartado:* um provedor ou modelo próprio para o juiz, configurado à parte. Criaria variáveis novas sem necessidade; os níveis já são o ponto de configuração dos modelos.
- *Descartado:* usar o mesmo nível `medium` da resposta. O juiz deve ser pelo menos tão capaz quanto o modelo avaliado.

### D6. Conferência com o `QueryRunner` e etapas encadeadas
`--check-expected` executa o `verify` de cada pergunta com o `QueryRunner` (mesmo validador, conexão somente leitura e `MATCH_TEXT`), sem modelo. Cada etapa pode usar `{previous}` no SQL, substituído pelos valores da primeira coluna da etapa anterior como lista de literais SQL escapados, e `{previous_count}`, o número de linhas dela (ex.: "2 de 20 bolsistas encontrados"). O resultado da última etapa é comparado com os critérios da pergunta pela coluna indicada em `column`; sem ela, `numbers` procura em todas as colunas e `list` usa a primeira. Para `numbers`, a resposta esperada diverge quando algum valor esperado não aparece; para `list`, quando faltam ou sobram itens.
- *Descartado:* recalcular as respostas esperadas a cada execução da avaliação, sem guardá-las. O arquivo versionado deixa explícito o que se espera, e uma mudança nos dados deve ser revisada por uma pessoa, não absorvida em silêncio.
- *Descartado:* reescrever o YAML com os valores novos. Perderia comentários e a revisão humana.

### D7. Relatório no terminal e em `evals/results/`
O terminal mostra uma linha por pergunta (acertos/repetições, tokens médios, chamadas, consultas e fontes) e os critérios que falharam. O JSON em `evals/results/<data-hora>.json` traz também o modelo de cada nível, as respostas e o SQL executado. `evals/results/` entra no `.gitignore`.
- *Descartado:* gravar os resultados no banco da Maria. São artefatos de desenvolvimento, não dados da aplicação.

### D8. Conjunto inicial de 22 perguntas em 8 categorias
As categorias têm pelo menos duas perguntas cada, para que um erro isolado não pareça uma piora da categoria inteira. A lista está em `tasks.md` (4.1 e 4.2):

| Categoria (tag) | Perguntas | O que testa |
|---|---|---|
| A. Fomento, agregações (`fomento-agregacao`) | 4 | `mv_bolsas_metricas` com soma de `quantidade`, status válidos, bolsa ativa, árvore de áreas |
| B. Simcc, totais (`simcc-totais`) | 3 | views canônicas em vez das tabelas base com coautores repetidos |
| C. Simcc, pesquisador (`simcc-pesquisador`) | 3 | tabelas base partindo de `researcher` |
| D. Busca textual (`busca-textual`) | 2 | `MATCH_TEXT` nas duas fontes |
| E. Entre fontes (`entre-fontes`) | 3 | ligação pelo Lattes e declaração do limite de 100 |
| F. Conceitos ambíguos (`issue-2`) | 3 | política da #2, ainda não implementada: devem falhar hoje |
| G. Honestidade com o dado (`dado-ausente`) | 2 | não inventar número para dado ausente |
| H. Segurança e LGPD (`lgpd`) | 2 | coluna `access: aggregate` e mascaramento de PII |

As quatro perguntas da issue #1 entram com os valores conferidos em 2026-10-28. Duas perguntas repetem quase literalmente exemplos few-shot do catálogo ("artigos por ano desde 2020" e "projetos sobre dengue") e levam a tag `exemplo`, para que o relatório separe a cópia de exemplo do raciocínio. As demais são escritas diferentes dos exemplos. O comando aceita `--tag` repetível para rodar um subconjunto.

Uma execução completa com `--repeat 3` custa cerca de 2,5 a 3 milhões de tokens. A meta é chegar a cerca de 40 perguntas conforme #2, #3 e #4 entram, transformando em pergunta cada erro real observado na demo.
- *Descartado:* um conjunto mínimo só com as perguntas da #1 e da #2. Deixaria sem medida as regras que a redução de contexto (#3) pode quebrar, como a soma de `quantidade` e as views canônicas.
- *Descartado:* começar com 50 ou mais perguntas. O custo por execução desestimularia rodar antes e depois de cada mudança.
- *Descartado nesta mudança:* perguntas de *prompt injection*, que exigiriam plantar texto nos bancos externos (somente leitura), e perguntas em vários turnos, que o formato de uma pergunta por conversa não cobre.

## Risks / Trade-offs

- [Variação do modelo entre execuções] → `--repeat N` e taxa de acerto por pergunta; comparar mudanças com o mesmo número de repetições.
- [Respostas esperadas desatualizadas quando o ETL do Simcc ou o fomento mudam] → `--check-expected` aponta as divergências; rodar antes de comparar execuções.
- [Juiz erra ou é leniente] → justificativa no relatório e critérios textuais curtos e verificáveis; o juiz não é usado para números ou listas.
- [Custo de cada execução, ~30 a 50 mil tokens por pergunta] → filtros por id e tag; a avaliação nunca roda no `task test` nem na CI.
- [Número formatado de forma inesperada, como "3,6 mil"] → o critério falha e o relatório mostra a resposta; ajustar a pergunta ou o extrator caso a caso.
- [Perguntas da #2 falham até a política existir] → é o comportamento esperado; a tag `issue-2` deixa isso explícito no relatório.
- [Cópia do SQLite durante escrita do servidor de dev] → copiar com a API de backup do `sqlite3`, que gera uma cópia consistente mesmo com WAL.
