# Tasks

## 1. Ligações entre fontes no catálogo

- [x] 1.1 Em `models.py`, criar `CatalogSourceLink` (D7) e a migração (autogenerate, revisada, nome em ASCII), testada com upgrade, downgrade e upgrade numa cópia do banco de dev. Em `schemas.py` e `routers/catalog.py`, criar `GET/POST /catalog/links` e `PATCH/DELETE /catalog/links/{id}`, com 422 para colunas inexistentes ou da mesma fonte e 409 para repetidas. Testes em `tests/test_catalog_links.py`: criar, listar, desligar, excluir, os erros e a sincronização preservando a ligação. Atualizar a seção **🗂️ Catálogo de dados** do README.
- [x] 1.2 Em `catalog/yaml_io.py`, aceitar `links` no arquivo de conceitos (`fonte:schema.entidade.coluna`) e incluí-los na exportação, com as regras de seed não destrutivo e `--reset`. Acrescentar a ligação pelo Lattes ao `catalog/concepts.yaml`. Testes: seed em catálogo vazio, ligação desligada mantida, coluna inexistente avisa, ida e volta, e o arquivo do repositório sem avisos.
- [x] 1.3 Em `catalog/context.py`, acrescentar a seção "Consultas entre fontes" (D8), só com ligações ativas e colunas visíveis e presentes, entre fontes incluídas. Testes: ligação ativa aparece; desligada, com coluna ausente ou com uma fonte fora não aparece.

## 2. Validador com vários catálogos

- [x] 2.1 Criar `build_federated_schema` e `validate_federated_query` (D3), com dialeto `duckdb`, e ajustar `_check_aggregate_columns` e `rewrite_match_text` para receberem a chave da tabela. Testes em `tests/test_query_federated_validation.py`, sem alterar os testes atuais de `test_query_validation.py`:
  - aceita consulta com `fonte.schema.tabela`;
  - recusa tabela sem o nome completo, uma fonte só, três fontes e fonte desativada;
  - recusa tabela oculta, coluna oculta e `*`;
  - recusa coluna `aggregate` exibida, inclusive com tabela de mesmo nome na outra fonte;
  - recusa `postgres_query`, `read_csv` e `FROM 'arquivo.csv'`;
  - `MATCH_TEXT` funciona em coluna pesquisável e é recusado nas demais.
- [x] 2.2 Implementar a regra de junção por ligação declarada (D4). Testes: aceita o Lattes nos dois sentidos, em `JOIN` e em `WHERE`; recusa instituições por nome, `CROSS JOIN`, outro operador entre fontes, ligação desligada e consulta sem junção entre as fontes.
- [x] 2.3 Gerar o SQL de cobertura (D6). Testes: consulta plana devolve o SQL com os filtros só da fonte de origem; filtro da outra fonte fica de fora; CTE ou subconsulta na origem devolve motivo em vez de SQL.

## 3. Execução no DuckDB

- [x] 3.1 Acrescentar `duckdb` ao `pyproject.toml`, e `QUERY_FEDERATED_MEMORY_LIMIT`, `QUERY_FEDERATED_THREADS` e `QUERY_FEDERATED_MAX_CONCURRENT` ao `settings.py`, com `.env.example` e a tabela de configuração do README. Criar `query/federation.py` (D2, D5): thread própria, sequência de configuração, `ATTACH` em `READ_ONLY` com `statement_timeout`, trava, tempo limite com `interrupt`, semáforo, limpeza de erros e fechamento garantido da conexão. Testes em `tests/test_query_federation.py`, com duas origens SQLite em arquivo (sem a extensão, pulados com aviso):
  - junção e agregação entre fontes, comparadas com o resultado calculado à mão;
  - `LIMIT` com truncamento;
  - mudança de configuração recusada depois da trava;
  - escrita na origem recusada, numa origem SQLite temporária;
  - leitura de arquivo recusada;
  - tempo limite interrompe a consulta;
  - memória excedida gera erro com orientação;
  - a terceira consulta espera com concorrência 2;
  - erro de conexão não contém a URL;
  - cobertura calculada e falha da cobertura sem derrubar o resultado.
- [x] 3.2 Instalar a extensão `postgres` no `Dockerfile` (D10) e atualizar `docs/deploy.md` (extensões e atualização de um servidor existente). Construir a imagem localmente e, dentro dela, conferir que `LOAD postgres` funciona sem rede.

## 4. Agente

- [x] 4.1 Em `query/tool.py`, criar `query_across_sources`, com o mesmo orçamento e a mesma sanitização de `query_data`, e `coverage` no resultado (D9). Ajustar `QueryObservation` e `_execute_tool_call`, a atividade com as duas fontes e o registro da ferramenta só com ligação ativa. Revisar as regras do prompt com a obrigação de cobertura. Testes em `tests/test_agent_chat.py` com modelo roteirizado: ferramenta presente e ausente, resultado alimentando gráfico, contagem para `QUERY_MAX_PER_CALL`, atividade sem SQL e fonte única sem mudança.
- [x] 4.2 Atualizar `catalog/simcc.yaml` e `catalog/fomento.yaml`: sai a orientação de passar até 100 Lattes e entra a da consulta entre fontes. Teste: as instruções não citam o limite. Atualizar o README (segurança e **Fomento × Simcc**).

## 5. Demo

- [x] 5.1 Na subaba "Conceitos", acrescentar a lista de ligações, com alerta de coluna ausente, e criar, ligar, desligar e excluir, seguindo o padrão da tela. Mostrar a prévia da nova seção.
- [x] 5.2 Verificar no navegador, no desktop e a 375px: desligar a ligação tira a seção da prévia, ligação inválida mostra o erro, e uma pergunta entre fontes mostra as duas fontes no andamento. Desfazer as edições de teste.

## 6. Avaliação

- [x] 6.1 Em `evaluation/`, fazer o critério `sources` usar `sources` da observação e aceitar `verify` entre fontes (`source: federated`). Testes com modelo falso e origens temporárias.
- [x] 6.2 Atualizar `evals/reference.yaml`:
  - `artigos-todos-doutorado` passa a esperar o total real, com `judge` para a cobertura;
  - `artigos-doutorado-uesc-2015` e `artigos-a1-doutorado-fiocruz` usam `verify` entre fontes;
  - acrescentar "Quantos artigos Qualis A1 publicaram os bolsistas, por modalidade de bolsa?", que agrupa por atributo da outra fonte, e uma pergunta que tenta cruzar instituições das duas fontes, com `judge` para a recusa.

  Conferir com `task eval -- --check-expected`.

## 7. Verificação final

- [x] 7.1 No banco de dev, aplicar `alembic upgrade head` e `task seed`, e as instruções pela API. Rodar `task eval -- --repeat 3` e registrar acertos e tokens. Critério: nenhuma pergunta abaixo da linha de base (65/66) e as perguntas entre fontes com menos tokens que os 30 a 68 mil de hoje.
- [x] 7.2 Contra os bancos de produção, só com leitura e sem deploy, rodar 3 consultas típicas e o pior caso sem filtro por um script temporário, com a conexão e os limites do executor. Registrar tempo, memória e duração na origem. Critério: pior caso dentro de `QUERY_TIMEOUT_SECONDS` e de `QUERY_FEDERATED_MEMORY_LIMIT`, ou encerrado por eles sem deixar consulta ativa na origem. Se não passar, ajustar os limites padrão antes de arquivar.
- [x] 7.3 Rodar `task test` (lint, testes e cobertura) sem falhas.

## Resultados da verificação (2026-10-30)

- **3.2:** imagem construída localmente; num container sem rede, `LOAD postgres` funcionou com o DuckDB 2.0.0.
- **5.2:** verificado no navegador, no desktop e a 375px, sem rolagem horizontal. Desligar a ligação tirou a seção da prévia, ligá-la de novo a devolveu, e uma ligação entre colunas da mesma fonte mostrou "Uma ligação precisa unir duas fontes diferentes". A pergunta "Quantos artigos publicaram, no total, os bolsistas de doutorado do fomento?", antes recusada, foi respondida com 119 artigos e cobertura de 26 em 3.653. A conversa de teste foi apagada.
- **7.1** (`gpt-6-luna` low, `--repeat 3`; relatório `evals/results/2026-10-30T12-46-03.json`): **69/72**, com o gabarito de 24 perguntas. `--check-expected` deu 19 ok e 5 sem conferência. Das 22 perguntas da linha de base, nenhuma ficou abaixo do resultado anterior; `artigos-todos-doutorado` agora tem critério mais difícil. Falhas, todas do modelo:
  - `artigos-doutorado-uesc-2015` (2/3): uma resposta usou uma junção errada com `MATCH_TEXT(a.title, 'title')` e deu 0 artigos, embora tenha informado a cobertura;
  - `artigos-todos-doutorado` (2/3): depois de dois erros de coluna, uma resposta desistiu de cruzar as fontes e disse que não conseguiu calcular;
  - `artigos-a1-por-modalidade` (2/3): uma resposta juntou uma subconsulta do fomento, o que impede o cálculo de cobertura. Os números estavam certos e a limitação foi declarada, mas faltou o 99 esperado.

  Custo por pergunta entre fontes: `artigos-doutorado-uesc-2015` de ~30 mil para ~19 mil tokens, com uma consulta só; `artigos-a1-doutorado-fiocruz` de ~50 mil para ~37 mil. `artigos-todos-doutorado` subiu de ~23 mil para ~36 mil, porque agora calcula o total em vez de declarar o limite. Perguntas de fonte única ficaram em ~19 mil, com a seção nova no prompt.
- **7.2:** verificação contra os bancos de produção, só com leitura, num container temporário, com os limites do executor (15 s, 512 MB, 2 threads):

  | Consulta | Tempo | Memória máxima |
  |---|---|---|
  | Artigos de todos os bolsistas de doutorado | 0,61 s | 101 MB |
  | Artigos A1 por modalidade | 0,72 s | 114 MB |
  | Artigos por ano pela view canônica | 0,89 s | 114 MB |
  | Pior caso, sem filtro | 0,69 s | 130 MB |

  `ATTACH` das duas fontes em menos de 0,1 s, e nenhuma consulta ativa de `maria_leitura` restou na origem. Os limites padrão foram mantidos.

- **7.3:** `task test` passou com 390 testes, lint limpo e 95% de cobertura (93% nos módulos de validação e execução entre fontes).

## Workflow follow-up

- Sincronizar as specs e arquivar com `/opsx:archive`.
- Commits: `docs(openspec): planeja add-consultas-entre-fontes`, depois `feat: ...` com "Implementa openspec/changes/add-consultas-entre-fontes." e por fim `docs(openspec): arquiva add-consultas-entre-fontes`.
- O deploy em produção é um pedido à parte, pelos passos de `docs/deploy.md`.
- Comentar o resultado na issue #4 e fechá-la.
