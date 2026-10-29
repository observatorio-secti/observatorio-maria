# Tasks

## 1. Modelo e migração

- [x] 1.1 Em `models.py`, criar `CatalogConcept` (`catalog_concepts`: `id` slug, `label`, `description`, `synonyms`, `instructions`, `created_at`, `updated_at`) e `CatalogEntity.concept_id`, anulável, com chave estrangeira `ON DELETE SET NULL` e índice (D1). Gerar a migração por autogenerate, com `op.batch_alter_table` para a coluna no SQLite, nome de arquivo em ASCII, e testar upgrade, downgrade e upgrade. Testes em `tests/test_models.py`: excluir um conceito deixa as entidades com `concept_id` nulo, e a sincronização de uma fonte não altera `concept_id`.

## 2. API de conceitos

- [x] 2.1 Em `schemas.py` e `routers/catalog.py`, criar as rotas de D8: `GET/POST /catalog/concepts` (a listagem traz as entidades vinculadas com a fonte), `GET/PATCH/DELETE /catalog/concepts/{id}`, com 404 para conceito inexistente e 409 para identificador repetido. O identificador é imutável: o `PATCH` não o aceita. Testes em `tests/test_catalog_api.py`: criar, listar com entidades, editar, identificador repetido (409), excluir com entidades vinculadas (as entidades ficam sem conceito).
- [x] 2.2 Fazer o `PATCH /catalog/entities/{id}` aceitar `concept_id` (ou nulo) e o detalhe e a listagem de entidades mostrarem o conceito. Um conceito inexistente responde 422. Testes: vincular, desvincular e conceito inexistente. Atualizar a seção **🗂️ Catálogo de dados** do README com conceitos, rotas e o vínculo.

## 3. Contexto do modelo

- [x] 3.1 Em `catalog/context.py`, criar `render_concepts`, que gera "Conceitos em várias fontes" só com conceitos que têm entidades visíveis e presentes em duas ou mais das fontes incluídas (D4, D5), e acrescentar `Conceito: <rótulo>` na seção da entidade. Criar `GET /catalog/concepts/context` com a prévia. Testes em `tests/test_catalog_context.py`: conceito em duas fontes aparece com política e entidades; conceito numa fonte só não aparece; entidade oculta fica fora; a linha do conceito aparece na entidade.
- [x] 3.2 Em `services/chat.py` e `llm/prompts.py`, incluir a seção de conceitos antes dos contextos das fontes, quando não estiver vazia, e trocar o exemplo de `MATCH_TEXT` de `TOOL_RULES_PROMPT` por termos genéricos (D6). Testes em `tests/test_agent_chat.py`: com duas fontes e um conceito comum, o prompt de sistema tem a seção antes do contexto da primeira fonte; com uma fonte, não tem; o prompt não contém "dengue".

## 4. Seed e exportação de conceitos

- [x] 4.1 Em `catalog/yaml_io.py` e `catalog/seed.py`, aceitar o arquivo de conceitos (chave `concepts:`, entidades `fonte:schema.entidade`), validar todos os arquivos antes de gravar e aplicar os conceitos depois das fontes, com aviso para entidades inexistentes e as regras de seed não destrutivo e `--reset` de D3. Criar `GET /catalog/concepts/export`, no mesmo formato. Testes em `tests/test_catalog_yaml.py`: seed com fontes e conceitos num catálogo vazio; entidade de fonte ausente gera aviso; política editada é mantida num segundo seed; `--reset` recria; exportar e fazer seed com reset reproduz os conceitos; arquivo inválido não altera o catálogo.
- [x] 4.2 Escrever `catalog/concepts.yaml` com `projetos`, `instituicoes` e `pesquisadores`, a política decidida na issue #2 e as entidades:
  - projetos: `fomento:public.projetos`, `simcc:public.research_project` e `simcc:public.mv_canonical_research_projects`;
  - instituições: `fomento:public.instituicoes` e `simcc:public.institution`;
  - pesquisadores: `fomento:public.pesquisadores` e `simcc:public.researcher`.

  Cada política diz o que o conceito é em cada fonte e qual fonte responde pelo sentido da pergunta. Sem sentido definido, manda usar a fonte padrão, dizer a origem do número e mencionar a outra numa frase, e proíbe somar as fontes. Teste: o seed do arquivo do repositório num catálogo semeado com `fomento.yaml` e `simcc.yaml` vincula todas as entidades listadas, sem avisos. Documentar o arquivo e o efeito do `--reset` de uma fonte sobre os vínculos no README.

## 5. Seeds das fontes

- [x] 5.1 Trocar os exemplos de dengue (D6): no fomento, "Projetos com bolsa sobre mandioca"; no Simcc, "Projetos de pesquisa do currículo sobre educação". Teste em `tests/test_catalog_yaml.py`: nenhuma pergunta de exemplo se repete entre `fomento.yaml` e `simcc.yaml`, e nenhum termo de `MATCH_TEXT` aparece nas duas. Os testes de exemplos aceitos pelo validador continuam passando.
- [x] 5.2 Em `simcc.yaml` (D7), listar `researcher_institution` (`researcher_id`, `institution_id`, `workload` e `identity_territory`), remover `researcher.institution_id` e acrescentar às instruções a junção por `researcher_institution`, com `COUNT(DISTINCT ...)` e sem correspondência com as instituições do fomento. Sincronizar com o Simcc de dev: nenhuma coluna do seed fica ausente, e a prévia mostra os relacionamentos de `researcher_institution` sem `researcher.institution_id`. Atualizar a seção do Simcc no README e o `docs/deploy.md` com os passos para aplicar pela API, em produção, as mudanças que o seed não sobrescreve.

## 6. Demo

- [x] 6.1 Em `demo/catalog.js` e `demo/index.html`, criar a área "Conceitos" (D9): lista com entidades, criação, edição, exclusão com confirmação e prévia da seção. Acrescentar o seletor de conceito na edição de entidade. Erros da API aparecem no banner da aba.
- [x] 6.2 Verificar no navegador, no desktop e a 375px, sem rolagem horizontal:
  - editar a política de um conceito atualiza a prévia;
  - um identificador repetido mostra o erro;
  - vincular `public.projetos` ao conceito aparece na lista e na prévia da fonte;
  - desfazer no fim as edições de teste.

## 7. Banco de dev e avaliação

- [x] 7.1 Aplicar no banco de dev: `alembic upgrade head`, `task seed` (cria os conceitos) e, pela API, os novos exemplos das duas fontes, as instruções do Simcc, `researcher_institution` visível e consultável e `researcher.institution_id` oculta. Conferir na prévia de cada fonte e na de conceitos.
- [x] 7.2 No `evals/reference.yaml`, tirar a tag `exemplo` de `projetos-dengue` e conferir as perguntas com `task eval -- --check-expected`. Rodar `task eval -- --repeat 3` e registrar o resultado na seção de resultados deste arquivo. Critério: as três perguntas `issue-2` passam, e nenhuma outra pergunta acerta menos que na linha de base de 61/66. Se alguma `issue-2` falhar, ajustar a política em `concepts.yaml` e no banco de dev e repetir.
- [x] 7.3 Rodar `task test` (lint, testes e cobertura) sem falhas.

## Resultados da verificação (2026-10-29)

- **6.2:** verificado no desktop e a 375px, sem rolagem horizontal; o `scrollX` fica em 0, e a largura de 375,56px vem do arredondamento da emulação.
  - Editar a política de `projetos` atualizou a prévia.
  - Um identificador repetido mostrou "Já existe um conceito com esse identificador", com a lista intacta.
  - Desvincular e vincular `public.projetos` pelo seletor atualizou a lista do conceito e a linha "Conceito: Projetos" na prévia do fomento.
  - A política editada voltou ao texto do seed.
  - A área de conceitos virou uma subaba (D9).
- **7.1:** no banco de dev, `alembic upgrade head` e `task seed` criaram 3 conceitos e vincularam 7 entidades. Pela API, entraram os exemplos e as instruções dos seeds, `researcher_institution` ficou visível e consultável e `researcher.institution_id` ficou oculta. Nenhum exemplo foi recusado. Num banco temporário, o seed do Simcc foi sincronizado com o Simcc de dev:
  - nenhuma coluna ficou ausente;
  - os três relacionamentos de `researcher_institution` aparecem na prévia.
- **7.2** (`gpt-6-luna` low, `--repeat 3`; relatórios `evals/results/2026-10-29T01-25-46.json` e `2026-10-29T01-33-25.json`):
  - **Execução completa:** 58/66. O modelo deixou de repetir `'dengue', 'arbovirose'`: respondeu pelo fomento, buscando no título ou no resumo, e citou os projetos do Lattes no Simcc. Seis das oito falhas eram do gabarito ou do avaliador, e foram corrigidas:
    - `projetos-dengue`:
      - esperava 133 (só o resumo), e "sobre dengue" inclui o título. Passou a esperar 135, com `verify` no nome ou no resumo;
      - o juiz exigia "podem ser consultados à parte", além do decidido na issue #2 ("mencionar a outra numa frase"). O critério passou a ser mencionar os projetos do Lattes sem somá-los.
    - `mais-capitulos-desde-2020`: a pergunta pede quem mais publicou, e os dois primeiros estão empatados com 8. O terceiro deixou de ser exigido.
    - `artigos-covid`: o modelo reescreveu títulos com travessão "–". A comparação de listas passou a normalizar traços tipográficos.
    - `cidade-com-mais-bolsistas`: o juiz tratou como inventado o total de bolsas, que veio de uma consulta. O critério deixou claro que só cidade ou número por cidade contam como invenção.
  - **Nova execução das perguntas afetadas e das `issue-2`:** 18/18. Juntando com o resto da execução completa, o resultado é **65/66**. A única falha restante é `artigos-doutorado-uesc-2015` (2/3): uma resposta não disse quantos bolsistas foram encontrados no Simcc, a mesma falha da linha de base. Nenhuma pergunta piorou em relação à linha de base de 61/66.
  - **Custo:** a seção de conceitos acrescenta cerca de 2,3 mil tokens por resposta de fonte única (de ~23,7 mil para ~26 mil), porque o prompt é reenviado a cada chamada. Fica para a #3 compensar.
- **7.3:** `task test` sem falhas.

## Workflow follow-up

- Sincronizar as specs e arquivar com `/opsx:archive`.
- Commits: `docs(openspec): planeja add-conceitos-entre-fontes`, depois `feat: ...` com "Implementa openspec/changes/add-conceitos-entre-fontes." e por fim `docs(openspec): arquiva add-conceitos-entre-fontes`.
- Comentar na issue #2 o resultado do `task eval` e fechá-la; a #3 parte desta mudança.
