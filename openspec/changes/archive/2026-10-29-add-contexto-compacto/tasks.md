# Tasks

## 1. Campo `list_values` e configuração

- [x] 1.1 Em `models.py`, criar `ValueListing` (`auto`, `always`, `never`) e `CatalogColumn.list_values` (`NOT NULL`, `server_default 'auto'`) (D1). Gerar a migração por autogenerate, revisada e com nome em ASCII, e testar upgrade, downgrade e upgrade numa cópia do banco de dev. Em `settings.py`, criar `CATALOG_CONTEXT_VALUES_MAX: int = Field(20, ge=1)`. Atualizar `.env.example` e a tabela **⚙️ Configuração** do README. Teste: um valor `0` é recusado na criação de `Settings`.
- [x] 1.2 Expor `list_values` em `ColumnPublic` e `ColumnUpdate` e no `ColumnDoc` do YAML (seed e exportação, omitido quando `auto`). Testes:
  - em `tests/test_catalog_api.py`: `PATCH` com `never` responde 200; com `sim` responde 422; a sincronização seguinte mantém o valor;
  - em `tests/test_catalog_yaml.py`: o seed aplica `list_values`; a exportação omite `auto` e mantém `never`; a ida e volta preserva o campo.

## 2. Contexto do modelo

- [x] 2.1 Em `catalog/context.py`, aplicar a regra de D2 em `_column_line`, recebendo `CATALOG_CONTEXT_VALUES_MAX` por parâmetro com padrão vindo de `Settings`, e usar o rótulo "Valores:" para toda coluna listada (D5). Revisar em `TOOL_RULES_PROMPT` a regra de usar os valores exatamente como listados. Testes em `tests/test_catalog_context.py` e `tests/test_catalog_enums.py`:
  - categoria curta é listada;
  - acima do limite, não é listada;
  - valores longos não são listados;
  - coluna pesquisável não é listada;
  - enum é listado mesmo acima do limite;
  - coluna com descrição editorial é listada;
  - `always` lista;
  - `never` não lista, nem enum;
  - o rótulo longo não aparece mais.

  Ajustar os testes existentes que esperam o rótulo antigo.
- [x] 2.2 Mover os relacionamentos para a linha da coluna de origem e remover a seção "Relacionamentos" (D4). Testes:
  - chave estrangeira simples aparece como `→ main.pesquisadores.id`;
  - relacionamento manual com descrição mostra a descrição;
  - composto aparece na primeira coluna;
  - ponta oculta, relacionamento desligado e coluna de origem oculta ficam fora;
  - não há seção "Relacionamentos".

  Atualizar a seção **🗂️ Catálogo de dados** do README (listagem de valores, regra automática e relacionamentos na coluna).

## 3. Seeds

- [x] 3.1 Medir, com o catálogo de dev, quais colunas a regra automática ainda lista, e marcar nos seeds `list_values: never` nas que não são categorias (D3). Teste em `tests/test_catalog_yaml.py`: toda coluna com `list_values` nos seeds existe no próprio seed, e `researcher.orcid` está como `never`. Num banco temporário, semear os dois seeds e sincronizar com os bancos de dev, conferindo que a prévia não lista ORCID, nomes de instituição, cidades nem JCR.

## 4. Demo

- [x] 4.1 Em `demo/catalog.js`, acrescentar a coluna "Valores no contexto" na tabela de colunas, com o seletor Automático, Sempre ou Nunca (D6). Erros da API aparecem no banner da aba.
- [x] 4.2 Verificar no navegador, no desktop e a 375px:
  - escolher "Nunca" numa coluna listada tira os valores da prévia;
  - escolher "Automático" devolve os valores;
  - não há rolagem horizontal fora da tabela, que já tem rolagem própria;
  - desfazer as edições de teste.

## 5. Banco de dev e medição

- [x] 5.1 Aplicar no banco de dev `alembic upgrade head` e, pela API, os `never` dos seeds. Medir o prompt de sistema com tiktoken `o200k_base` e registrar, na seção de resultados, regras, conceitos, cada fonte e listas de valores. Meta: 8 mil tokens ou menos.
- [x] 5.2 Rodar `task eval -- --check-expected` e `task eval -- --repeat 3`. Registrar acertos e tokens médios por pergunta. Critério: nenhuma pergunta abaixo do resultado da `add-conceitos-entre-fontes` (65/66). Se cair, investigar se foi um valor que deixou de ser listado e ajustar a marcação.
- [x] 5.3 Rodar `task test` (lint, testes e cobertura) sem falhas.

## Resultados da verificação (2026-10-29)

- **3.1:** num banco temporário, os dois seeds foram sincronizados com os bancos de dev, e a prévia não lista ORCID, nomes, cidades, editoras, JCR, códigos nem datas. Fora as 19 colunas marcadas como `never`, a regra automática já excluía `state.abbreviation` (27 valores), títulos de patentes e softwares (longos) e colunas pesquisáveis. `institution.acronym` (10 siglas) continua listada: é usada em filtros e sai sozinha quando passar de 20.
- **4.2:** verificado no navegador. Em `bibliographic_production_article.qualis`, "Nunca" tirou os valores da prévia e "Automático" os devolveu. A 375px, a página não rola na horizontal; a tabela de colunas rola dentro do próprio quadro, como antes. A coluna voltou para `auto`.
- **5.1:** no banco de dev, `alembic upgrade head` e os `never` dos seeds aplicados pela API (2 colunas no fomento e 17 no Simcc). Prompt de sistema (tiktoken `o200k_base`):

  | Parte | Antes | Depois |
  |---|---|---|
  | Total | 12.425 | **8.789** (−29%) |
  | Regras | 551 | 600 |
  | Conceitos | 755 | 755 |
  | Fomento | 3.471 | 2.801 |
  | Simcc | 7.639 | 4.624 |
  | Linhas com valores | 4.767 | ~1.230 |

  A meta de 8 mil não foi atingida. O que sobra está em instruções (948), exemplos (575), conceitos e nas entidades duplicadas entre tabelas base e views canônicas do Simcc, fora do escopo desta etapa. O usuário aceitou os 8,8 mil como resultado. A descrição de um relacionamento igual à da coluna deixou de se repetir na linha.
- **5.2** (`gpt-6-luna` low, `--repeat 3`; relatórios `evals/results/2026-10-29T09-13-34.json` e `2026-10-29T09-21-43.json`): `--check-expected` deu 18 ok e 4 sem conferência.
  - **Execução completa:** 62/66. A média de tokens por pergunta de fonte única caiu de ~26 mil para ~18,8 mil (−28%), e a execução inteira gastou 1,47 milhão de tokens, contra 2,02 milhões antes. As quatro falhas não vieram de consulta errada: o SQL estava certo em todas.
    - `artigos-a1-desde-2022` (1/3): em duas respostas, o modelo mostrou só tabela ou gráfico por ano (2, 2, 1, 7, 6) e não escreveu o total 18 que a pergunta "quantos" pede. `qualis` continuou com os valores listados.
    - `artigos-doutorado-uesc-2015` (1/3): a mesma falha da linha de base, sem dizer "2 de 20 encontrados".
  - **Nova execução das duas:** `artigos-a1-desde-2022` 3/3 e `artigos-doutorado-uesc-2015` 2/3, os mesmos níveis das etapas anteriores. A queda foi variação do modelo, não efeito da compactação. Com o mesmo critério da `add-conceitos-entre-fontes` (perguntas que caíram executadas de novo), o resultado equivale a 65/66.
  - Fica registrado um modo de falha a acompanhar: em perguntas de total, o modelo às vezes responde só com gráfico ou tabela, sem o número no texto.
- **5.3:** `task test` passou com 329 testes, lint limpo e 96% de cobertura.

## Workflow follow-up

- Sincronizar as specs e arquivar com `/opsx:archive`.
- Commits: `docs(openspec): planeja add-contexto-compacto`, depois `feat: ...` com "Implementa openspec/changes/add-contexto-compacto." e por fim `docs(openspec): arquiva add-contexto-compacto`.
- Comentar na issue #3 o resultado da primeira etapa. A issue continua aberta para a segunda (índice de entidades e `describe_entities`).
