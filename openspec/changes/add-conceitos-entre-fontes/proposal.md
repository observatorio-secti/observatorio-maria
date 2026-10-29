# Proposal

## Why

Com o fomento e o Simcc, o mesmo nome aparece nas duas fontes com significados diferentes: "projetos" são projetos com bolsa no fomento e projetos do currículo Lattes no Simcc; o mesmo vale para instituições e pesquisadores. Hoje nada orienta o modelo sobre qual usar. A linha de base do `task eval` (#1) mostra o efeito: `projetos-dengue` acerta 0/3 e `total-pesquisadores` 2/3. Para piorar, o mesmo exemplo "Projetos de pesquisa sobre dengue" está no seed das duas fontes e nas regras do prompt, com `MATCH_TEXT(p.resumo, 'dengue', 'arbovirose')`, e o modelo o copia, inclusive o termo extra. O problema cresce a cada fonte nova e afeta a redução de contexto (#3). As decisões estão na issue #2.

## What Changes

- **Conceitos no catálogo:** nova entidade editorial do catálogo, o *conceito* (ex.: `projetos`), com rótulo, descrição, sinônimos e política de resposta. Cada entidade pode apontar para um conceito. Conceitos são dado editorial: a sincronização nunca os altera.
- **API de conceitos:** criar, listar, detalhar, editar, excluir e exportar conceitos; o `PATCH` de entidade aceita o conceito.
- **Seed `catalog/concepts.yaml`:** cria os conceitos `projetos`, `instituicoes` e `pesquisadores`, com a política decidida (fonte padrão pelo sentido da pergunta e menção da outra fonte numa frase) e as entidades de cada fonte. É carregado pelo `task seed` depois das fontes e segue as regras de seed não destrutivo.
- **Contexto do modelo:**
  - o prompt de sistema ganha a seção "Conceitos em várias fontes", com a política de cada conceito que tenha entidades em pelo menos duas fontes incluídas;
  - cada entidade com conceito indica o conceito no contexto da sua fonte;
  - uma prévia da seção de conceitos fica disponível na API e na demo.
- **Exemplos sem tema repetido:** o exemplo de dengue sai dos dois seeds e das regras do prompt. O fomento ganha um exemplo de busca com outro tema, o Simcc também, e as regras do prompt passam a usar termos genéricos.
- **Simcc com `researcher_institution`:** o Simcc trocou `researcher.institution_id` pela tabela N:N `researcher_institution`. O seed expõe a nova tabela e seus relacionamentos e deixa de expor `researcher.institution_id`. As instruções orientam a junção pela nova tabela, com `COUNT(DISTINCT ...)` nas contagens de pesquisadores.
- **Demo:** a aba "Catálogo de dados" ganha a lista e a edição de conceitos, a escolha do conceito de cada entidade e a prévia da seção de conceitos.
- **Gabarito:** as perguntas `issue-2` deixam de ter a tag `exemplo`. As consultas de conferência com instituição passam a usar `researcher_institution`, quando houver.

### Fora do escopo

- Correspondência entre instituições do fomento e do Simcc: fica para as consultas entre fontes (#4).
- Carregar entidades sob demanda e compactar o contexto (#3). Esta mudança só deixa o conceito pronto para a #3 levar ao contexto as entidades irmãs.
- Conceitos além dos três decididos; novos são criados pela API ou pela demo.

## Capabilities

### New Capabilities

Nenhuma.

### Modified Capabilities

- `data-catalog`: conceitos (modelo, API, seed, exportação, prévia e contexto), seed do Simcc com `researcher_institution` e exemplos sem tema repetido entre fontes.
- `conversation-messaging`: seção de conceitos no prompt de sistema.
- `demo-page`: lista, edição e prévia de conceitos e conceito da entidade na aba do catálogo.

## Impact

- **Código:**
  - `models.py`: modelo `CatalogConcept` e `CatalogEntity.concept_id`;
  - `catalog/yaml_io.py` e `catalog/seed.py`: arquivo de conceitos;
  - `catalog/context.py`: seção de conceitos e linha do conceito na entidade;
  - `routers/catalog.py` e `schemas.py`: rotas de conceitos;
  - `llm/prompts.py`: regras sem o exemplo de dengue;
  - `services/chat.py`: monta a seção de conceitos;
  - `demo/catalog.js` e `demo/index.html`: a interface.
- **Seeds:** `catalog/concepts.yaml` (novo), `catalog/fomento.yaml` e `catalog/simcc.yaml`.
- **Banco da Maria:** migração que cria `catalog_concepts` e adiciona `catalog_entities.concept_id`. Dados existentes não mudam; entidades ficam sem conceito até o seed ou a edição. O banco de dev recebe os conceitos pelo seed e os ajustes de exemplos e do Simcc pela API, porque o seed não sobrescreve fontes existentes.
- **Bancos externos:** nenhum acesso novo além de ler `researcher_institution` do Simcc, somente leitura.
- **Segredos:** nenhum.
- **Endpoints sem autenticação:** as novas rotas `/catalog/concepts` nascem sem autenticação, como o resto do catálogo, enquanto o observatorio-idp não estiver pronto.
- **Avaliação:** critério de pronto é `task eval -- --repeat 3` com as três perguntas `issue-2` passando e nenhuma outra piorando em relação à linha de base de 61/66.
- **Dependências:** depende da `add-perguntas-de-referencia`, já arquivada. A mudança da #3 vai depender desta.
