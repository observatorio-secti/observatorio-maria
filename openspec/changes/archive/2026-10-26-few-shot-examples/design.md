# Design: Exemplos de Consulta Validados (Few-shot) no Catálogo

## Arquitetura e Decisões

### 1. Modelo de Dados e Armazenamento

- **Abordagem:** Armazenar `examples` como coluna JSON na tabela `catalog_datasources` em `src/observatorio_maria/models.py`:
  ```python
  examples: Mapped[list[dict[str, str]]] = mapped_column(
      JSON, default_factory=list, server_default=text("'[]'")
  )
  ```
  Cada item na lista segue a estrutura:
  ```json
  {
    "question": "Pergunta em linguagem natural",
    "sql": "SELECT ... FROM ...;"
  }
  ```
- **Alternativa descartada:** Criar uma tabela relacional separada `catalog_examples`.
- **Motivo do descarte:** O catálogo já utiliza colunas JSON para campos compostos leves (`schemas`, `synonyms`). Uma fonte tipicamente possui entre 3 e 6 exemplos canônicos. Uma tabela relacional separada exigiria operações adicionais de join/selectin, endpoints dedicados de sub-recursos e chaves estrangeiras sem ganho prático de performance ou integridade.

### 2. Contratos da API e Pydantic Schemas

- Adicionar em `src/observatorio_maria/schemas.py`:
  ```python
  class QueryExample(BaseModel):
      question: str = Field(description='Pergunta em linguagem natural.')
      sql: str = Field(description='Instrução SQL canônica correspondente.')
  ```
- Integrar nos modelos:
  - `DataSourceCreate`: `examples: list[QueryExample] = Field(default_factory=list)`
  - `DataSourceUpdate`: `examples: list[QueryExample] | None = None`
  - `DataSourcePublic`: `examples: list[QueryExample] = Field(default_factory=list)`

### 3. Integração com YAML (Seed e Exportação)

- Atualizar `src/observatorio_maria/catalog/yaml_io.py`:
  - `dump_datasource()`: serializa a lista `examples` sob a chave `datasource.examples`.
  - `load_datasource()`: extrai e valida a lista `examples` ao fazer o parse do YAML.
- Atualizar `catalog/fomento.yaml` com 4 exemplos curados:
  1. Contagem de bolsas ativas por modalidade.
  2. Total de bolsas por ano utilizando `mv_bolsas_metricas`.
  3. Busca textual de projetos por tema usando `MATCH_TEXT`.
  4. Projetos vinculados a pesquisadores com Lattes preenchido.

### 4. Renderização do Contexto (`render_context`)

- Em `src/observatorio_maria/catalog/context.py`:
  ```python
  if datasource.examples:
      lines += ['', '## Exemplos de consultas (few-shot)']
      for eg in datasource.examples:
          q = eg.get('question', '').strip()
          sql = eg.get('sql', '').strip()
          if q and sql:
              lines.append(f'- Pergunta: "{q}"')
              lines.append('  ```sql')
              lines.append(f'  {sql}')
              lines.append('  ```')
  ```
- Isso garante que tanto a prévia do catálogo (`GET /catalog/datasources/{id}/context`) quanto as instruções de sistema da Maria (`build_system_prompt`) recebam a formatação idêntica em Markdown.

## Migration Plan

- **Migração Alembic:** Gerar migração adicionando a coluna `examples` (tipo `JSON`, com default `'[]'`) em `catalog_datasources`.
- **Compatibilidade:** Retrocompatível com bases existentes, preenchendo fontes legadas com lista vazia.

## Riscos e Mitigações

- `[Risco: Exemplos desatualizados ou inválidos quebrarem a consulta do modelo] → Mitigação:` Os exemplos são validados e curados por humanos no seed e mantidos em conjunto com a evolução do schema.
- `[Risco: Aumento do consumo de tokens no prompt do sistema] → Mitigação:` De 3 a 5 exemplos curados consomem aproximadamente 200 a 350 tokens, o que representa menos de 1% da janela de contexto típica de modelos modernos, trazendo um ganho desproporcionalmente maior na taxa de acerto de primeira.
