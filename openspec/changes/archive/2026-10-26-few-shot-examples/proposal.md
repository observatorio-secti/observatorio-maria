# Proposal: Exemplos de Consulta Validados (Few-shot) no Catálogo

## Why

Modelos de linguagem encarregados de traduzir perguntas em linguagem natural para consultas SQL (Text-to-SQL) frequentemente enfrentam desafios ao lidar com peculiaridades de regras de negócio, convenções de status e sintaxes proprietárias de cada banco de dados.

No módulo de fomento, por exemplo:
- Para contagem correta de bolsas ativas, certas categorias de status devem ser incluídas (`REGULAR`, `RESOLVIDA`, `PENDENTE_REVISAO`), enquanto outras devem ser excluídas (`DESCARTADA`).
- Para agregações analíticas de volume, a view materializada `mv_bolsas_metricas` deve ser preferida somando `quantidade`, em vez de disparar `COUNT(*)` sobre tabelas brutas.
- Para buscas textuais, deve-se usar `MATCH_TEXT(coluna, 'termo')`.

Embora as instruções textuais em linguagem natural já auxiliem, **exemplos canônicos de pergunta e SQL (few-shot validado por humanos)** são comprovadamente o meio mais eficiente e de menor custo cognitivo para ancorar a IA, eliminando alucinações de sintaxe e tentativas incorretas.

## What Changes

- **Armazenamento de Exemplos no Catálogo:** Adicionar o campo `examples: list[dict[str, str]]` em `CatalogDataSource` (`catalog_datasources.examples` no banco da Maria), guardando pares estruturados de pergunta e consulta SQL validada.
- **Migração de Banco de Dados:** Criar migração Alembic para adicionar a coluna `examples` com valor padrão `[]` na tabela `catalog_datasources`.
- **Suporte no Formato YAML do Catálogo:** Atualizar `yaml_io.py` para suportar `examples:` no seed YAML (ex.: `catalog/fomento.yaml`) e na exportação (`GET /catalog/datasources/{id}/export`).
- **Exposição na API do Catálogo:** Incluir o campo `examples` nos schemas `DataSourceCreate`, `DataSourceUpdate` e `DataSourcePublic`, permitindo que curadores visualizem e editem os exemplos via API e demo.
- **Injeção no Contexto do Modelo (`render_context`):** Atualizar `src/observatorio_maria/catalog/context.py` para renderizar a seção `## Exemplos de consultas (few-shot)` com as perguntas e blocos SQL formatados quando a fonte possuir exemplos cadastrados.
- **Seed com Exemplos Iniciais do Fomento:** Adicionar de 3 a 5 exemplos representativos no arquivo `catalog/fomento.yaml` cobrindo contagem de bolsas, busca com `MATCH_TEXT` e agregações com `mv_bolsas_metricas`.

### Fora do escopo

- Sistema dinâmico de RAG semântico para recuperar exemplos de banco vetorial (com 3 a 5 exemplos por fonte, a injeção direta no contexto da fonte é mais simples, determinística e não exige dependências vetoriais extras).
- Validação automática periódica dos SQLs de exemplo contra o banco de origem (a curadoria é manual por humanos).

## Capabilities

### Modified Capabilities

- `data-catalog`: O catálogo passa a suportar o registro, persistência, seed/exportação YAML e exibição de exemplos canônicos de pergunta e SQL por fonte de dados.
- `conversation-messaging`: O contexto enviado ao modelo de IA passa a incluir a seção de exemplos few-shot da fonte consultável ativa.

## Impact

- **Banco da Maria:** Uma nova coluna JSON `examples` na tabela `catalog_datasources` via migração Alembic.
- **Precisão da IA:** Aumento expressivo da taxa de acerto na primeira consulta SQL formulada pela Maria, reduzindo chamadas adicionais e tempo de resposta.
- **Contratos da API:** Retrocompatível; o campo `examples` é opcional com lista vazia por padrão.
