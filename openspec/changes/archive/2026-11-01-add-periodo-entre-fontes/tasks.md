# Tasks

## 1. Comparação de ordem entre fontes

- [x] 1.1 Adicionar a `FederatedSchema` as colunas de data e número, montadas em `build_federated_schema`, e verificar com teste dos tipos do Postgres e do SQLite.
- [x] 1.2 Aceitar em `_check_cross_source` as comparações de ordem com colunas rastreadas ordenáveis, incluindo `EXTRACT` e `BETWEEN`, e verificar com os cenários de aceite em `tests/test_query_federated_validation.py`.
- [x] 1.3 Manter as recusas de ordem sem ligação, coluna de texto, `<>` e `LIKE`, e verificar com testes de recusa, mantendo os testes atuais de ligação.
- [x] 1.4 Testar a consulta plana por período até a execução em `tests/test_query_federation.py` e verificar que `coverage` vem preenchida e sem a comparação entre fontes.
- [x] 1.5 Atualizar o parágrafo Fomento × Simcc do `README.md` com a nova regra e conferir que ele cita os operadores aceitos e os recusados.

## 2. O que a Maria sabe

- [x] 2.1 Acrescentar a `render_source_links` o alcance do limite, a orientação de agregar e a preferência pela forma plana, e verificar em `tests/test_catalog_links.py`.
- [x] 2.2 Incluir na política de `pesquisadores` em `catalog/concepts.yaml` a receita e as ressalvas da produção durante a bolsa, e verificar em `tests/test_catalog_concepts_yaml.py`.
- [x] 2.3 Corrigir no README a orientação de contexto e registrar que a política nova vai à produção pela API, conferindo com `poetry run task test`.

## 3. Avaliação

- [x] 3.1 Adicionar a `evals/reference.yaml` a pergunta de artigos durante a bolsa e a de todos os bolsistas, com os valores obtidos por `task eval -- --check-expected` no banco de dev, e verificar que o arquivo carrega.
- [ ] 3.2 Rodar `poetry run task eval` e comparar com a linha de base de 65/66, confirmando as duas perguntas novas e nenhuma regressão.
- [x] 3.3 Medir o tamanho do prompt depois da mudança e registrar o resultado, comparando com os 8,8 mil tokens atuais.
- [ ] 3.4 Rodar em produção, só com leitura, a consulta plana por período e registrar tempo e memória, confirmando que ficam dentro de 15 s e 512 MB.
- [x] 3.5 Rodar `poetry run task test` e `openspec validate add-periodo-entre-fontes --strict` sem falhas.

## Workflow follow-up

- Pendência da 3.2 (2026-10-30): o eval completo não rodou porque o Simcc de dev ficou sem tabelas durante a avaliação. Faltam confirmar `artigos-a1-por-modalidade` com a política final (1/3 antes da correção) e comparar `projetos-dengue` (1/3) com a versão anterior. O usuário decidiu seguir sem esse eval.
- Fazer o deploy e aplicar a política de `pesquisadores` pela API.
- Arquivar a mudança depois da revisão.
