# Design

## Context

Motivação em `proposal.md`. Estado atual relevante:

- **Valores no contexto:** em `catalog/context.py`, `_known_values` devolve os valores da origem (enum ou observados) com as descrições editoriais, ou os valores editoriais quando a origem não informa nada. `_column_line` lista todos. Com valores observados, o rótulo é "Valores existentes na origem (use exatamente como estão)", repetido em 53 colunas.
- **Valores observados:** são lidos de colunas de texto visíveis, presentes e com acesso `full`, sempre que o número de valores distintos fica em até `CATALOG_OBSERVED_VALUES_MAX` (50). A demo usa esses valores para revisar descrições, e eles não entram na impressão digital.
- **Relacionamentos:** `render_context` lista os relacionamentos ligados entre entidades incluídas numa seção própria no fim, repetindo nomes que já estão nas colunas. São 356 tokens no fomento e 357 no Simcc.
- **Regras do prompt:** `TOOL_RULES_PROMPT` já manda usar os valores de colunas de texto exatamente como listados no catálogo.
- **Medição no dev** (tiktoken `o200k_base`): prompt total de 12.425 tokens, sendo 551 de regras, 755 de conceitos, 3.471 do fomento e 7.639 do Simcc. As listas de valores somam 4.767 tokens em 55 colunas. As maiores são:

  | Coluna | Tokens |
  |---|---|
  | `researcher.orcid` | 411 |
  | `institution.name` | 279 |
  | `territorios_identidade.nome` | 258 |
  | `city.name` | 235 |
  | `jcr` (duas tabelas) | 205 cada |
  | `publishing_company` (duas tabelas) | 199 cada |

## Goals / Non-Goals

**Goals:**
- O tamanho do prompt deixa de crescer com colunas que não são categorias.
- Pessoas podem corrigir a decisão automática coluna a coluna.

**Non-Goals:**
- Escolher entidades por pergunta: isso é a segunda etapa da #3.
- Reduzir as instruções das fontes e os exemplos, que são regras de negócio.

## Decisions

### D1. Campo `list_values` com três estados
`catalog_columns.list_values` é texto com `auto`, `always` ou `never` (`StrEnum ValueListing`), `NOT NULL` com `server_default 'auto'`. É editorial: não é tocado pela sincronização, aparece no `ColumnPublic`, no `ColumnUpdate`, no `ColumnDoc` do YAML (omitido na exportação quando é `auto`) e na demo.
- *Descartado:* booleano anulável (`None` = automático). Três estados explícitos ficam mais legíveis na API, no YAML e na demo.
- *Descartado:* reaproveitar `access` ou `visible`. Esconder valores não muda o que o modelo pode consultar nem se ele enxerga a coluna.

### D2. Regra automática
Com `auto`, a coluna lista valores quando:
1. tem enum na origem; ou
2. tem algum valor com descrição editorial; ou
3. tem valores observados, não é pesquisável, tem no máximo `CATALOG_CONTEXT_VALUES_MAX` valores e a média de caracteres dos valores é até 30.

Sem valores da origem, os valores editoriais continuam listados, como hoje. `always` lista o que `_known_values` devolver, e `never` não lista nada.
- *Descartado:* baixar `CATALOG_OBSERVED_VALUES_MAX`. A demo deixaria de mostrar os valores para revisão, e colunas curtas que não são categorias (datas, JCR) continuariam entrando.
- *Descartado:* só o limite de quantidade. `patent.title` tem 4 valores longos no dev, e títulos nunca são categoria.
- *Descartado:* a média de 30 caracteres como configuração. É um detalhe da heurística; quem precisar de exceção usa `always` ou `never`.

`CATALOG_CONTEXT_VALUES_MAX` (padrão 20) vai para `settings.py`, `.env.example` e o README, como o limite de leitura.

### D3. Seeds marcam o que não é categoria
`fomento.yaml` e `simcc.yaml` recebem `list_values: never` nas colunas visíveis de texto que não são categorias e que ainda passariam pela regra automática no dev, ou que passariam com mais dados. A lista final sai da medição na implementação. O ponto de partida é: `orcid`; `institution.name`; `city.name`; `state.name`; `publishing_company` e `publishing_company_city`; `jcr`; datas de patente guardadas como texto; `territorios_identidade.nome` e `nome_normalizado`.
- *Descartado:* depender só da regra. Com mais dados, uma coluna de nomes pode cair abaixo do limite numa fonte pequena; a marcação deixa a decisão explícita.

### D4. Relacionamentos na linha da coluna
A linha da coluna de origem termina com `→ schema.entidade.coluna` (com todas as colunas, separadas por vírgula, nos compostos), e a descrição do relacionamento, se houver, entra entre parênteses. A seção "Relacionamentos" sai. Valem só relacionamentos ligados, presentes e com as duas entidades incluídas, como hoje. Se a coluna de origem estiver oculta, o relacionamento não aparece. Hoje ele aparece mesmo nesse caso, e mostrar uma junção por coluna oculta não ajuda, porque o validador recusaria a consulta.
- *Descartado:* manter a seção em formato curto. Cada linha repetiria nomes de entidade e de coluna que já estão nas linhas das colunas.

### D5. Rótulo "Valores:" e regra única
Toda coluna com valores listados usa o rótulo "Valores:". A orientação de usar os valores como estão fica só em `TOOL_RULES_PROMPT`, que já a contém; o texto é revisado para cobrir enum e valores observados.
- *Descartado:* manter o rótulo longo só nos valores observados. São 53 repetições da mesma frase.

### D6. Demo
A tabela de colunas da entidade ganha a coluna "Valores no contexto", com um seletor (Automático, Sempre, Nunca) que faz `PATCH /catalog/columns/{id}`. A prévia é atualizada como nos outros interruptores.
- *Descartado:* pôr o seletor dentro do editor de valores, que só abre em colunas com valores e esconderia a opção.

## Risks / Trade-offs

- [Uma coluna categórica deixa de listar valores e o modelo filtra com um valor errado] → O aviso de resultado vazio já manda conferir com `SELECT DISTINCT`. O `task eval` mede a precisão, e `always` resolve casos pontuais.
- [Com o Simcc completo, os números do dev mudam] → A regra e as marcações não dependem de o banco ser pequeno; a medição é refeita quando o Simcc completo estiver disponível (issue #5).
- [Relacionamentos na linha da coluna ficam menos visíveis que numa seção própria] → O `task eval` cobre perguntas com junção (pesquisador, entre fontes). Se a precisão cair, a seção volta em formato curto.

## Migration Plan

1. A migração (autogenerate, revisada) adiciona `catalog_columns.list_values` `String(10) NOT NULL server_default 'auto'`, sem `batch_alter_table`, porque não há chave estrangeira. As colunas existentes ficam em `auto`.
2. No banco de dev, os `never` dos seeds são aplicados pela API.
3. **Rollback:** `alembic downgrade -1` remove a coluna, e o contexto volta a listar tudo assim que o código anterior é reimplantado. Testar com upgrade, downgrade e upgrade.
