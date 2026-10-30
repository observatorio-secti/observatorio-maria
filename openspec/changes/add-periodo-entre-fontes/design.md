# Design

## Context

`_check_cross_source` percorre as comparações da consulta. Só `=` e `IN (subconsulta)` entre colunas da ligação passam; qualquer outra comparação com colunas rastreadas de duas fontes é recusada. Colunas calculadas não têm origem rastreada e escapam da checagem, por isso a mesma pergunta passa dentro de uma CTE. Com CTE, `_coverage_query` não calcula a cobertura.

`query_across_sources` aplica `QUERY_MAX_ROWS` só ao resultado final. O contexto do modelo não explica isso, e os exemplos do catálogo são validados contra uma fonte só, então não podem ter SQL entre fontes.

## Goals / Non-Goals

**Goals:**
- Aceitar a forma plana da pergunta de vigência, com cobertura.
- Impedir que a Maria alegue um limite de pesquisadores que não existe.

**Non-Goals:**
- Rastrear a origem de colunas calculadas.
- Mudar `QUERY_MAX_ROWS` ou os limites do DuckDB.

## Decisions

**Comparação de ordem aceita por tipo de coluna.** Uma comparação `>`, `>=`, `<`, `<=` ou `BETWEEN` entre fontes passa quando todas as colunas rastreadas são de data ou número, e a consulta segue obrigada a ter ao menos uma ligação. `FederatedSchema` ganha o conjunto de colunas ordenáveis, montado a partir de `data_type`. Alternativa descartada: declarar no catálogo pares de colunas comparáveis, porque cada pergunta nova exigiria configuração, e o risco que a regra evita (juntar por texto parecido) não existe em datas e números junto de uma chave real.

**Colunas rastreadas dentro de expressões.** `EXTRACT(YEAR FROM b.quando_iniciou)` conta como a coluna `quando_iniciou`, cujo tipo é data. Alternativa descartada: exigir coluna pura dos dois lados, porque o artigo só tem ano e a pergunta principal seguiria recusada.

**Regra genérica no código, receita no conceito.** O alcance do limite vai em `render_source_links`, por valer para qualquer ligação e chegar à produção com o deploy. A receita de bolsa e artigo vai na política de `pesquisadores`, editável pela API, porque é regra de domínio. Alternativa descartada: exemplo few-shot na fonte, recusado por `check_examples`, que valida uma fonte só.

**Bolsa sem término.** A receita usa `b.quando_terminou IS NULL OR bp.year_ <= EXTRACT(YEAR FROM b.quando_terminou)`. Alternativa descartada: `COALESCE` com `CURRENT_DATE`, que o validador não permite e que nem é necessário.

**Coautores.** A contagem usa `COUNT(DISTINCT COALESCE(NULLIF(bp.doi, ''), LOWER(bp.title) || '-' || CAST(bp.year_ AS TEXT)))`, porque as tabelas base têm uma linha por autor. Alternativa descartada: `mv_canonical_articles`, que não identifica o autor e não se liga ao pesquisador.

## Risks / Trade-offs

- [Comparação por ano aceita artigo de um ano em que a bolsa cobriu só parte dos meses] → A política manda declarar a comparação por ano.
- [Vigência lida como financiamento] → A política manda dizer que vigência não prova financiamento.
- [Cobertura baixa faz o total parecer a produção de todos os bolsistas] → A cobertura sai na resposta, como nas demais consultas entre fontes.
- [Produção publicada sob grafias diferentes sem DOI conta duas vezes] → Aceito: a contagem é uma aproximação, melhor que repetir por coautor.
- [Regra por tipo depende do `data_type` do catálogo] → A coluna sem tipo reconhecido é recusada, e o teste cobre os tipos do Postgres e do SQLite.
- [Cruzamento mais pesado que o medido] → Vale o tempo limite de 15 s e a memória de 512 MB; a tarefa 3.4 mede em produção, só com leitura.
- [Desvio por CTE continua aberto] → Sem piora: ele já existe, está fora do escopo e a orientação ao modelo prefere a forma plana.

- [Prompt maior] → A mudança soma cerca de 1,5 mil caracteres, estimados em 500 tokens, sobre os 8,8 mil atuais. Estimativa por caracteres, não medição no prompt real.

## Migration Plan

Sem migração de banco. Depois do deploy, aplicar a política nova de `pesquisadores` pela API, pois o seed não sobrescreve. Para reverter, voltar o commit e restaurar a política anterior pela API.

## Open Questions

- Considerar `data_saida_pesquisador` como fim da vigência. Hoje a regra de bolsa ativa só usa `quando_terminou`, e a receita segue essa decisão. Pode ser ajustado depois só na política.
