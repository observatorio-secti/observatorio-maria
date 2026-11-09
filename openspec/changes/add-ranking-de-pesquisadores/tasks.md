# Tasks

## 1. Contrato do bloco `researchers`

- [x] 1.1 Adicionar `RankingInfo` (`term`, `criterion`, `fields`, `data_as_of`) e `ResearcherEvidence` (`total`, `by_type`, `items` com `type`, `title`, `year`) em `schemas.py`, como campos opcionais de `ResearchersBlock` e `ResearcherCard`, e verificar com teste que um bloco gravado sem eles continua válido.
- [x] 1.2 Atualizar o contrato do bloco `researchers` na seção 🌐 API do `README.md` e conferir o exemplo de JSON contra os schemas.

## 2. Consulta de ranking (`query/ranking.py`)

- [x] 2.1 Montar a consulta de ranking sobre `mv_search_documents` e `mv_researcher_search` com a fórmula da V2, filtros de período, tipos e ids de instituição, desempate por nome e id, `total` e limite de 1 a 20 (padrão 10). Verificar compilando para o dialeto PostgreSQL que o termo e os filtros vão como parâmetros e que, com tipos, o perfil não entra.
- [x] 2.2 Montar a consulta de evidências da página (até 3 por pesquisador, perfil como `PROFILE` quando casa e não há filtro de tipo) e a contagem por tipo, e verificar compilando que ficam restritas aos ids da página.
- [x] 2.3 Implementar a resolução de instituição por sigla ou nome sem acento e sem caixa, a verificação de disponibilidade das views (`to_regclass` e existência de linhas) e a leitura da data em `mv_refresh_metadata`, tolerando a tabela ausente. Verificar com testes de compilação e, para a data, com origem SQLite temporária com e sem a tabela.

## 3. Ferramenta `search_researchers`

- [x] 3.1 Criar `SearchResearchersInput` e `QueryRunner.search_researchers` em `query/tool.py`: termo obrigatório, fonte `simcc` ativa em PostgreSQL, orçamento de consultas, limite de tempo, erros sem URL, resultado no `ResultStore` com envelope `<untrusted_database_data>` e bloco `researchers` com `ranking` e `evidence` na ordem do ranking, hidratado por `hydrate_researchers`.
- [x] 3.2 Repassar a chamada em `services/chat.py` com atividade de consulta ao Simcc, span de ferramenta e métrica de consulta, e incluir a ferramenta em `build_query_tools`.
- [x] 3.3 Testar com repositório falso e fakes do LangChain: ordem preservada, evidências e perfil, data presente e ausente, views indisponíveis sem bloco, instituição desconhecida, termo vazio, fonte inativa, limite acima de 20, orçamento esgotado e título com instrução dentro do envelope.

## 4. Orientação ao modelo e catálogo

- [x] 4.1 Orientar em `llm/prompts.py` o uso de `search_researchers` em perguntas por tema, a explicação do critério com a data e a resposta quando pedem ordem por Qualis, citações ou índice h; verificar com teste que o prompt traz as orientações.
- [x] 4.2 Atualizar `catalog/simcc.yaml`: trocar a instrução de buscas temáticas por `search_researchers` e remover os exemplos temáticos de pesquisadores sem ordem. Verificar com teste de seed e prévia de contexto.
- [x] 4.3 Adicionar cenários de avaliação para "especialistas em dengue" e "pesquisadores com mais artigos" em `evaluation/` quando o formato das perguntas de referência permitir, e verificar com os testes de avaliação.
- [x] 4.4 Atualizar a seção 🗂️ Catálogo de dados do `README.md` (ranking, views usadas, dependência do refresh) e `docs/deploy.md` (como aplicar a instrução nova em catálogos já semeados).

## 5. Demo

- [x] 5.1 Renderizar em `demo/app.js` e `demo/styles.css` as evidências de cada card (total, contagem por tipo em português, itens com tipo, título e ano; perfil como "Resumo do currículo") e o aviso de ordem acima dos cards com campos, ressalva sobre Qualis, citações e índice h e data em pt-BR.
- [x] 5.2 Incluir o total de produções sobre o tema no CSV do bloco e `ranking` e `evidence` no exemplo da aba de contrato.
- [x] 5.3 Verificar no navegador streaming, conversa reaberta, lista sem `ranking`, CSV e aba de contrato em desktop e a 375px, nos temas claro e escuro.

  Verificado em 2026-11-09 com o modelo real e as views locais preenchidas: "Quem são os especialistas em dengue na Bahia?" gerou o bloco com 10 cards, evidências e o aviso ("os 10 mais relevantes de 815"), igual no streaming e na conversa reaberta, sem rolagem horizontal a 375px. A demo só tem tema claro (requisito "Tema claro" da demo-page), então não há tema escuro a verificar. Na primeira resposta, o texto citava os nomes fora da ordem dos cards; o prompt passou a pedir a ordem do ranking e descrições só pelas evidências (requisito "Pesquisadores do ranking no texto"), e a segunda resposta seguiu as duas regras.

## 6. Verificação contra o Simcc real

- [x] 6.1 Depois do refresh das views no Simcc local, rodar `search_researchers` para "dengue", "educação" (termo amplo) e "inteligência artificial" na UFBA, somente leitura, registrar tempos e conferir a ordem contra `GET /v2/researcher?q=...&sort_by=relevance` do simcc-back.
- [x] 6.2 Rodar `poetry run task test` (lint, testes e cobertura) sem falhas.

  Resultado em 2026-11-09, banco local `simcc_write` (views preenchidas; `mv_refresh_metadata` sem linhas, então `data_as_of` nulo), três execuções da Maria contra a V2 sem cache:

  | Busca | Total | Maria (ms) | V2 (ms) | Ordem dos 20 primeiros |
  |---|---|---|---|---|
  | dengue | 815 | 98, 50, 40 | 405 | idêntica |
  | educação | 20.514 | 330, 269, 253 | 793 | idêntica |
  | inteligência artificial na UFBA (35 instituições) | 170 | 60, 52, 54 | 75 | idêntica |

  A V2 foi chamada com `collection=all`. Com o padrão dela (`collection=simcc`), "dengue" dá 383 e "educação" 8.124; ver decisão 10 do design.
