# Proposal

## Why

Com o fomento, o Simcc e os conceitos, o prompt de sistema tem cerca de 12,4 mil tokens (tiktoken `o200k_base`, catálogo de dev) e é reenviado a cada chamada ao modelo, de 2 a 4 por resposta. Cada pergunta de fonte única gasta ~26 mil tokens. O maior peso são as listas de valores das colunas: 4,8 mil tokens em 55 colunas. As listas mais caras nem são categorias: ORCID, nomes de instituições e cidades, títulos de patentes, datas e JCR. Elas entram só porque o banco de dev tem poucas linhas, então o tamanho do prompt depende do volume de dados, e não do que o modelo precisa. Esta é a primeira etapa da issue #3: compactar o contexto antes de carregar entidades sob demanda.

## What Changes

- **Listagem de valores por coluna:** novo campo editorial `list_values` em cada coluna, com três opções:
  - `auto`, o padrão: segue a regra automática abaixo;
  - `always`: sempre lista os valores conhecidos;
  - `never`: nunca lista os valores.

  O campo pode ser editado pela API, pela demo e pelo YAML (seed e exportação). A sincronização não o altera.
- **Regra automática:** com `auto`, uma coluna lista valores quando é enum, quando tem valores com descrição editorial ou quando os valores observados parecem uma categoria. Para parecer uma categoria, a coluna não pode ser pesquisável, precisa ter no máximo `CATALOG_CONTEXT_VALUES_MAX` valores (padrão 20) e os valores precisam ter, em média, até 30 caracteres. A leitura dos valores observados continua como hoje (`CATALOG_OBSERVED_VALUES_MAX`); muda só o que entra no contexto.
- **Seeds:** `list_values: never` nas colunas que não são categorias, como ORCID, nomes de instituições, cidades e estados, editoras, JCR, datas e territórios do fomento.
- **Texto mais curto:**
  - a linha de cada coluna com valores passa a dizer só "Valores:". A orientação de usar os valores exatamente como listados já está nas regras do prompt e deixa de se repetir em cada coluna;
  - os relacionamentos passam a aparecer na linha da coluna de origem (`→ public.researcher.id`), e a seção "Relacionamentos" sai. Relacionamentos sem coluna visível nas duas pontas continuam fora.
- **Demo:** seletor "Listar valores" (automático, sempre, nunca) em cada coluna, na aba do catálogo.
- **Medição:** a meta inicial era levar o prompt de sistema com as duas fontes no dev a **8 mil tokens ou menos**, sem que o `task eval -- --repeat 3` fique abaixo de 65/66. O resultado foi 8.789 tokens, e o usuário aceitou o valor como resultado desta etapa (2026-10-29). O restante fica para a segunda etapa da #3.

### Fora do escopo

- Índice de entidades e ferramenta `describe_entities` (segunda etapa da #3, numa mudança própria).
- Remover entidades duplicadas entre tabelas base e views canônicas do Simcc.
- Mudar a leitura dos valores observados ou `CATALOG_OBSERVED_VALUES_MAX`.

## Capabilities

### New Capabilities

Nenhuma.

### Modified Capabilities

- `data-catalog`: listagem de valores por coluna (campo editorial, regra automática, seeds), relacionamentos na linha da coluna e texto de valores mais curto na prévia do contexto.
- `demo-page`: seletor de listagem de valores por coluna.

## Impact

- **Código:**
  - `models.py`: `CatalogColumn.list_values`;
  - `schemas.py` e `routers/catalog.py`: o campo no `PATCH` e na leitura da coluna;
  - `catalog/yaml_io.py`: o campo no seed e na exportação;
  - `catalog/context.py`: a regra de listagem e os relacionamentos na linha da coluna;
  - `settings.py`: `CATALOG_CONTEXT_VALUES_MAX`;
  - `demo/catalog.js`: o seletor.
- **Seeds:** `catalog/fomento.yaml` e `catalog/simcc.yaml`.
- **Banco da Maria:** a migração adiciona `catalog_columns.list_values`, com padrão `auto`. As colunas existentes ficam em `auto`. O banco de dev recebe os `never` dos seeds pela API, porque o seed não sobrescreve colunas existentes.
- **Bancos externos:** nenhum acesso novo.
- **Segredos:** nenhum.
- **Endpoints sem autenticação:** nenhum novo. O `PATCH /catalog/columns/{id}` passa a aceitar `list_values`.
- **Configuração:** `CATALOG_CONTEXT_VALUES_MAX` vai para o `.env.example` e para a tabela de configuração do README.
- **Dependências:** depende da `add-conceitos-entre-fontes`, já arquivada. A mudança do contexto sob demanda (segunda etapa da #3) vem depois desta.
