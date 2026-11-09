# Design

## Context

- A busca temática de pesquisadores hoje é SQL escrito pelo modelo (`MATCH_TEXT` vira `LIKE` com índice trigram) e apresentado por `show_researchers`, que hidrata os cards na ordem dos ids recebidos (`query/cards.py`).
- O validador não permite `ts_rank`, `ln`, `to_tsvector` nem funções de janela, e o limite de custo (`QUERY_MAX_ESTIMATED_COST`, 100 mil) recusaria agregações de termos amplos. Medido localmente, o ranking de "educação" estima custo de 114 mil e roda em 1,2 s.
- O simcc-back mantém `mv_search_documents` (uma linha por produção e autor, com `search_vector` e índice GIN; tipos `ARTICLE`, `BOOK`, `BOOK_CHAPTER`, `PATENT`, `SOFTWARE`, `PARTICIPATION_EVENT`, `AREA_SPECIALTY`), `mv_researcher_search` (`profile_vector`, `institution_ids` e outros arrays com GIN) e `mv_refresh_metadata` (`view_name`, `refreshed_at`). O refresh em produção é periódico e confiável; no banco local as views estão vazias até o próximo refresh.
- A fórmula de relevância da V2 está em `simcc-back/src/simcc/v2/repositories/researcher_repo.py` (`_relevance_score`, `fetch_matches`).

## Goals / Non-Goals

**Goals:**
- Mesma ordem que a V2 do Simcc para o mesmo termo e filtros, com a V2 em todas as coleções (decisão 10).
- Critério fixo no código; o modelo escolhe só termo e filtros.
- Uma consulta de ranking e uma de evidências por chamada, com tempo previsível em termos amplos.

**Non-Goals:**
- Paridade com todos os filtros e ordenações da V2.
- Expor a pontuação numérica ao usuário: ela só serve para ordenar.

## Decisions

### 1. Ler as views da V2 em vez das tabelas base
O ranking lê `mv_search_documents` e `mv_researcher_search`. **Alternativa descartada:** pré-filtrar `bibliographic_production.title` com trigram e calcular `to_tsvector` na hora. Cobriria só títulos (o resumo do OpenAlex sem índice custa cerca de 2 s), com semântica de substring e uma fórmula diferente da V2, o que daria ordens diferentes entre a Maria e o Simcc.

### 2. Ferramenta dedicada com SQL fixo, fora do validador
`search_researchers` monta a consulta com SQLAlchemy Core e parâmetros vinculados (`query/ranking.py`), sem passar pelo validador nem pelo dry-run de custo. **Alternativa descartada:** liberar `ts_rank` e afins no validador e ensinar a fórmula no prompt. O modelo variaria pesos e filtros entre respostas, e o limite de custo recusaria termos amplos. O dry-run não se aplica porque a consulta é conhecida e apoiada em índices; o limite de tempo continua valendo.

### 3. Agregação única com junção completa entre produções e perfil
```sql
WITH docs AS (
  SELECT researcher_id, count(*) AS n, max(ts_rank(search_vector, :tsq)) AS best
  FROM mv_search_documents
  WHERE search_vector @@ :tsq [AND year_ BETWEEN ...] [AND source_type IN ...]
  GROUP BY researcher_id),
prof AS (                                -- só sem filtro de tipo
  SELECT researcher_id, ts_rank(profile_vector, :tsq) AS rk
  FROM mv_researcher_search WHERE profile_vector @@ :tsq)
SELECT r.researcher_id, r.name, coalesce(docs.n, 0) AS n,
       coalesce(prof.rk, 0) * 1.5 + coalesce(docs.best, 0) + ln(coalesce(docs.n, 0) + 1) AS score,
       count(*) OVER () AS total
FROM docs FULL JOIN prof USING (researcher_id)
JOIN mv_researcher_search r USING (researcher_id)
[WHERE r.institution_ids && :institution_ids]
ORDER BY score DESC, r.name, r.researcher_id LIMIT :limit
```
`:tsq` é `websearch_to_tsquery('pt_unaccent', :term)`. **Alternativa descartada:** subselect correlacionado por pesquisador; a própria V2 documenta que ele repete a varredura do GIN e custa dezenas de segundos em termos amplos.

### 4. Evidências numa segunda consulta restrita à página
Para os ids da página, uma consulta com `row_number() OVER (PARTITION BY researcher_id ORDER BY ts_rank DESC, source_id)` traz até 3 produções, unida ao perfil (tipo `PROFILE`, título vazio) quando ele casa e não há filtro de tipo; outra agrupa por `source_type` para `by_type`. **Alternativa descartada:** trazer evidências na mesma consulta do ranking; a janela rodaria sobre todos os candidatos, não só sobre a página.

### 5. A ferramenta cria o bloco
`search_researchers` reaproveita `hydrate_researchers` para os dados do card, acrescenta `evidence` a cada card e `ranking` ao bloco, e registra o resultado no `ResultStore` (colunas `id`, `name`, `produções_sobre_o_tema`) para reapresentação. **Alternativa descartada:** devolver só um `result_id` para o modelo chamar `show_researchers`; as evidências se perderiam ou exigiriam um protocolo entre as duas ferramentas, e o modelo poderia reordenar a lista.

### 6. Instituição resolvida antes do ranking
A sigla ou o nome é comparado sem acento e sem caixa com `institution.acronym` e `institution.name`. No Simcc, unidades são instituições à parte ("Escola de Enfermagem - UFBA"; "UFBA" casa com 35 linhas no banco local). Por isso, quando há correspondência exata de sigla ou nome, entram também as unidades cujo nome contém o texto, até 200. Sem correspondência exata, mais de 20 instituições é ambíguo ("Bahia") e gera erro pedindo a sigla. Os ids filtram `institution_ids` com `&&`. Nenhuma correspondência gera erro explicado ao modelo. **Alternativa descartada:** passar o texto direto como `MATCH_TEXT` no nome do pesquisador ou da instituição dentro do ranking; misturaria a busca do tema com a da instituição.

### 7. Disponibilidade e data dos dados
Antes do primeiro ranking da resposta, a ferramenta verifica com `to_regclass` se as duas views existem e se `mv_search_documents` tem ao menos uma linha, e guarda o resultado no `QueryRunner`. A data é o menor `refreshed_at` entre as duas views em `mv_refresh_metadata`; erro ou ausência da tabela deixa a data nula. **Alternativa descartada:** cair para as tabelas base quando as views estão vazias; manteria dois critérios de ordem para a mesma pergunta.

### 8. Campos da ordem descritos no código
O texto dos campos considerados (títulos das produções, palavras-chave e resumos dos artigos, áreas de atuação, nome e resumo do currículo) é uma constante alinhada às definições das views da V2 e vai em `ranking.fields`. **Alternativa descartada:** deduzir os campos lendo a definição das views; exigiria analisar SQL de view no Simcc a cada chamada para um texto que muda raramente.

### 9. Testes sem PostgreSQL na suíte
A suíte testa a montagem do SQL (parâmetros, filtros, ausência de concatenação de texto do usuário) compilando para o dialeto PostgreSQL, e testa a ferramenta com um repositório falso (ranking, evidências, data e disponibilidade). A consulta real é verificada contra o Simcc local depois do refresh. **Alternativa descartada:** emular `tsvector` no SQLite; não existe equivalente e o teste não provaria a ordem real.

### 10. Todas as coleções, e não só a coleção `simcc`
O Simcc separa os pesquisadores em coleções (`mv_researcher_search.collection_slugs`): no banco local, 10.740 só em `simcc`, 30.309 só em `fomento` (bolsistas da Fapesb importados), 1.228 nas duas e 23 em nenhuma. Por padrão, a busca V2 filtra `collection=['simcc']`. A Maria não filtra coleção, por decisão do usuário: o ranking cobre todos os pesquisadores da base, como as demais consultas da Maria ao Simcc. **Alternativa descartada:** seguir o padrão da V2; os totais e a lista bateriam com o front do Simcc, mas os bolsistas da Fapesb ficariam fora do ranking. Verificado no banco local: com `collection=all` na V2, totais e ordem dos 20 primeiros são idênticos.

## Risks / Trade-offs

- [Views defasadas entre refreshes] → a data dos dados aparece no bloco, no aviso da demo e na explicação do modelo.
- [Mudança de colunas ou tipos das views na V2] → erro do banco vira mensagem genérica ao modelo, sem URL; a verificação manual na tarefa final cobre o contrato atual, e o README registra a dependência.
- [Termos amplos favorecem quem publica muito] → é o mesmo comportamento da V2, aceito para manter a paridade; o modelo pode sugerir período para refinar.
- [Termo só com palavras vazias ("de", "a") gera `tsquery` vazia] → nenhum pesquisador casa e o modelo recebe a dica de resultado vazio para reformular.
- [O modelo continuar usando `query_data` para temas] → instrução no prompt e no seed, sem exemplo temático sem ordem, e cenários de avaliação.
- [Suíte sem PostgreSQL não pega erro de SQL em tempo de execução] → teste de compilação no dialeto PostgreSQL e verificação manual registrada nas tarefas.

## Migration Plan

- Sem migração no banco da Maria e nada novo nos bancos externos.
- Deploy: publicar o código e atualizar a instrução da fonte `simcc` nos catálogos já semeados (pela API/demo, ou `task seed -- --reset` quando não houver edições a preservar), como descrito no `docs/deploy.md`.
- Rollback: voltar o código. Blocos gravados com `ranking` e `evidence` continuam legíveis, porque os modelos de bloco ignoram campos desconhecidos.
