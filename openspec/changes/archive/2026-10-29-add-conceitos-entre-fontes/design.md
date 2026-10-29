# Design

## Context

Motivação em `proposal.md`. Estado atual relevante:

- **Catálogo:** `CatalogDataSource`, `CatalogEntity`, `CatalogColumn` e `CatalogRelationship` em `models.py`. Campos editoriais (rótulo, descrição, sinônimos, visibilidade) ficam separados dos técnicos, e a sincronização só toca os técnicos. Itens novos entram ocultos.
- **Seed:** `task seed` roda `catalog.seed` sobre `catalog/*.yaml`. Cada arquivo tem `datasource:` e é validado por `CatalogFile` em `yaml_io.py`. Todos os arquivos são validados antes de gravar qualquer um. O seed cria o que falta, e `--reset` recria a fonte.
- **Contexto:** `render_context` gera o texto de uma fonte. `get_consultable_sources_and_contexts` junta as fontes ativas com entidades consultáveis, e `build_system_prompt` monta as regras, a data e os contextos. A prévia por fonte é `GET /catalog/datasources/{id}/context`.
- **Exemplos repetidos:** "Projetos de pesquisa sobre dengue" está em `fomento.yaml` e `simcc.yaml`. Além disso, `TOOL_RULES_PROMPT` ilustra `MATCH_TEXT(p.resumo, 'dengue', 'arbovirose')`. Na linha de base, o modelo repetiu esse filtro e respondeu 162 em vez de 133.
- **Simcc de dev:** `researcher_institution` (`researcher_id`, `institution_id`, `identity_territory`, `workload`, `city_id`; chave primária composta e chaves estrangeiras para `researcher`, `institution` e `city`) tem as mesmas 33 ligações de `researcher.institution_id`. No catálogo da Maria, a tabela está presente, mas oculta.
- **Demo:** `demo/catalog.js` tem as telas de fonte, entidades, colunas, relacionamentos e prévia.
- **Migrações:** geradas por autogenerate; o `env.py` não usa `render_as_batch`.

## Goals / Non-Goals

**Goals:**
- O modelo sabe, para cada conceito repetido, o que ele significa em cada fonte e como responder.
- O vínculo entre entidade e conceito serve à #3: carregar uma entidade sob demanda também traz as irmãs do mesmo conceito.

**Non-Goals:**
- Correspondência de registros entre fontes (instituições): #4.
- Roteamento automático de fontes pela política: a política é texto para o modelo, não regra executada pelo servidor.

## Decisions

### D1. Conceito como tabela própria, com vínculo N:1 na entidade
A tabela `catalog_concepts` tem `id` (slug), `label`, `description`, `synonyms`, `instructions` (a política), `created_at` e `updated_at`. `catalog_entities` ganha `concept_id`, uma chave estrangeira anulável com `ON DELETE SET NULL`. Uma entidade tem no máximo um conceito; um conceito reúne entidades de várias fontes.
- *Descartado:* um campo de texto `concept` na entidade. Não teria onde guardar rótulo e política, e erros de digitação criariam conceitos diferentes.
- *Descartado:* tabela de associação N:N. Nenhum caso atual precisa de uma entidade em dois conceitos, e o N:1 simplifica o seed, a API e a #3.

### D2. Política como texto livre
`instructions` é texto em Markdown, como as instruções das fontes. A fonte padrão fica dita na política, não num campo estruturado.
- *Descartado:* campo `default_datasource_id`. A escolha depende do sentido da pergunta (financiamento ou currículo), o que um campo único não expressa. Se a #3 precisar de estrutura, ela entra lá.

### D3. Seed em `catalog/concepts.yaml`, aplicado depois das fontes
Formato:

```yaml
concepts:
  - id: projetos
    label: Projetos
    description: ...
    synonyms: [projeto, projeto de pesquisa]
    instructions: |
      - ...
    entities: [fomento:public.projetos, simcc:public.research_project, simcc:public.mv_canonical_research_projects]
```

`seed.py` identifica o tipo de cada arquivo pela chave de topo (`datasource` ou `concepts`) e valida todos antes de gravar. Depois aplica primeiro as fontes e por último os conceitos, para as entidades já existirem. Entidades que não estão no catálogo geram aviso e são ignoradas. Sem `--reset`, o seed cria só os conceitos que faltam e vincula só entidades sem conceito. Com `--reset`, recria os conceitos do arquivo e seus vínculos; isso só vale quando o arquivo de conceitos está entre os arquivos passados.
- *Descartado:* campo `concept` em cada entidade dos YAMLs de fonte. A política teria de ficar num deles ou ser repetida, e o seed de uma fonte dependeria de outra.
- *Descartado:* conceitos dentro de um dos arquivos de fonte. O conceito é, por definição, de mais de uma fonte.

### D4. Seção global no prompt e linha na entidade
`render_concepts` gera a seção "Conceitos em várias fontes", com rótulo, descrição, política e, por fonte, as entidades do conceito. A seção entra em `build_system_prompt` antes dos contextos das fontes, para a política ser lida antes das entidades. Em `render_context`, a seção da entidade ganha a linha `Conceito: <rótulo>`. A prévia da seção global é `GET /catalog/concepts/context`.
- *Descartado:* escrever a política nas instruções de cada fonte. Seria repetida em cada fonte e sairia de sincronia ao editar.
- *Descartado:* só a seção global. A #3 vai enviar entidades isoladas, e a linha na entidade mantém o vínculo visível.

### D5. Só conceitos presentes em duas ou mais fontes incluídas
A seção lista um conceito só se ele tiver entidades visíveis e presentes em pelo menos duas fontes ativas com entidades consultáveis, que são as mesmas fontes do prompt. Com uma fonte só, não há ambiguidade a resolver.
- *Descartado:* listar todos os conceitos sempre. Gastaria tokens com políticas que comparam fontes ausentes do prompt.

### D6. Exemplos com temas distintos e regra genérica
- **Fomento:** "Projetos de pesquisa sobre dengue" vira "Projetos com bolsa sobre mandioca", com `MATCH_TEXT(resumo, 'mandioca')`. O tema não está no gabarito, que usa licuri.
- **Simcc:** o exemplo de dengue vira "Projetos de pesquisa do currículo sobre educação", com `MATCH_TEXT(title, 'educação')` em `mv_canonical_research_projects`.
- **Prompt:** `TOOL_RULES_PROMPT` passa a ilustrar `MATCH_TEXT(coluna, 'termo1', 'termo2')`.

Os exemplos são conferidos com o validador (requisito existente). No banco de dev, que já tem as fontes, os exemplos são trocados pela API.
- *Descartado:* manter dengue numa fonte só. "Projetos sobre dengue" é justamente a pergunta ambígua do gabarito; um exemplo com ela ensinaria a resposta.

### D7. `researcher_institution` no seed do Simcc
`simcc.yaml` lista `researcher_institution`, com `researcher_id` e `institution_id` (só para junção), `workload` e `identity_territory`. Deixa de listar `researcher.institution_id`. Os relacionamentos vêm das chaves estrangeiras da origem pela sincronização. As instruções do Simcc ganham a regra de junção e de `COUNT(DISTINCT r.id)`. No banco de dev, a entidade é tornada visível e consultável e `researcher.institution_id` é ocultada pela API. Quando o Simcc remover a coluna, a sincronização a marcará como ausente sozinha.
- *Descartado:* manter `researcher.institution_id` visível durante a transição. O modelo usaria o vínculo antigo, que deixa de existir e não representa várias instituições.

### D8. Rotas de conceitos
`GET/POST /catalog/concepts`, `GET /catalog/concepts/context`, `GET /catalog/concepts/export`, `GET/PATCH/DELETE /catalog/concepts/{id}`. As rotas fixas vêm antes de `/{id}` no router. `PATCH /catalog/entities/{id}` aceita `concept_id`. Sem autenticação, como o resto do catálogo, enquanto o observatorio-idp não estiver pronto.
- *Descartado:* conceitos aninhados em `/catalog/datasources/{id}`. O conceito não pertence a uma fonte.

### D9. Demo
O painel de detalhes da aba do catálogo ganha a subaba "Conceitos", ao lado de "Fonte". Na implementação ela substituiu a área acima da escolha de fonte prevista de início, porque cabe melhor a 375px e segue o padrão das outras visões. A subaba tem:
- a lista de conceitos e suas entidades;
- o formulário de criação e edição (identificador só na criação, rótulo, descrição, sinônimos e política);
- a exclusão com confirmação;
- a prévia da seção.

A edição de entidade ganha um seletor de conceito.
- *Descartado:* uma aba própria. Conceitos e entidades são editados juntos, e a aba do catálogo já tem o padrão de formulário e prévia.

## Risks / Trade-offs

- [O modelo ignora a política e continua respondendo sem citar a origem] → As três perguntas `issue-2` do `task eval` são o critério de pronto. Se não passarem, a política é ajustada no seed (texto) antes de arquivar.
- [A seção de conceitos aumenta o prompt em ~300 tokens] → A #3 vai reduzir o resto do contexto. Os conceitos só entram com duas fontes incluídas (D5).
- [O banco de dev e o de produção não recebem os exemplos e o Simcc do seed, que não sobrescreve] → Uma task aplica pela API as mesmas mudanças no dev. O README e `docs/deploy.md` descrevem os passos para produção.
- [O Simcc remove `researcher.institution_id` antes ou depois desta mudança] → A coluna já sai do contexto agora, e a ausência é tratada pela sincronização. Consultas a `researcher_institution` funcionam nos dois estados.
- [Seed com `--reset` só de uma fonte desvincula entidades recriadas dos conceitos] → Recriar a fonte apaga as entidades, e com elas os vínculos. O seed seguinte, com `concepts.yaml`, vincula de novo as entidades sem conceito. Isso fica documentado no README.

## Migration Plan

1. A migração (autogenerate, revisada) cria `catalog_concepts` e adiciona `catalog_entities.concept_id`, anulável, com chave estrangeira `ON DELETE SET NULL` e índice. No SQLite, a coluna com chave estrangeira usa `op.batch_alter_table`.
2. Dados existentes: nenhuma entidade muda; todas ficam sem conceito.
3. Depois do `alembic upgrade head`, `task seed` cria os conceitos e os vínculos sem tocar nas fontes existentes.
4. **Rollback:** `alembic downgrade -1` remove a coluna e a tabela. Os conceitos e os vínculos se perdem, e o resto do catálogo fica intacto. Testar com upgrade, downgrade e upgrade.
