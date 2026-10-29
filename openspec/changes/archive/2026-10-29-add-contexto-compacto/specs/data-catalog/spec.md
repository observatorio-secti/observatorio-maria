## ADDED Requirements

### Requirement: Listagem de valores por coluna
Cada coluna SHALL ter o campo editorial `list_values`, com os valores `auto` (padrão), `always` ou `never`, editável pela API e pelo YAML de seed e exportação. Um valor fora desses MUST ser recusado com 422. A sincronização MUST NOT alterar o campo.

#### Scenario: Nunca listar
- **WHEN** o cliente define `list_values` como `never` numa coluna com valores observados
- **THEN** o sistema responde 200 e a prévia do contexto não lista os valores da coluna

#### Scenario: Valor inválido
- **WHEN** o cliente define `list_values` como `sim`
- **THEN** o sistema responde 422

### Requirement: Regra automática de listagem de valores
Com `list_values` em `auto`, uma coluna SHALL listar valores no contexto se tiver enum ou valores com descrição editorial. Com só valores observados, SHALL listá-los apenas se a coluna não for pesquisável, tiver no máximo `CATALOG_CONTEXT_VALUES_MAX` valores (padrão 20) e os valores tiverem até 30 caracteres em média.

#### Scenario: Categoria curta
- **WHEN** `qualis` tem 10 valores observados curtos, não é pesquisável e está em `auto`
- **THEN** a prévia lista os 10 valores

#### Scenario: Muitos valores
- **WHEN** uma coluna em `auto` tem 38 valores observados e o limite é 20
- **THEN** a prévia não lista os valores

#### Scenario: Valores longos ou coluna pesquisável
- **WHEN** uma coluna em `auto` tem 4 títulos observados com 53 caracteres em média, ou é pesquisável
- **THEN** a prévia não lista os valores

#### Scenario: Sempre listar
- **WHEN** a coluna com 38 valores observados está em `always`
- **THEN** a prévia lista os 38 valores

### Requirement: Configuração do limite de valores no contexto
O sistema SHALL ler `CATALOG_CONTEXT_VALUES_MAX` (inteiro, mínimo 1, padrão 20) da configuração. O limite vale só para o que entra no contexto; a leitura e o armazenamento dos valores observados continuam regidos por `CATALOG_OBSERVED_VALUES_MAX`.

#### Scenario: Limite configurado
- **WHEN** `CATALOG_CONTEXT_VALUES_MAX` é 5 e uma coluna em `auto` tem 6 valores observados curtos
- **THEN** a prévia não lista os valores, e os 6 continuam guardados na coluna

### Requirement: Seeds sem listagem de valores não categóricos
Os seeds do fomento e do Simcc SHALL marcar com `list_values: never` as colunas visíveis de texto que não são categorias: identificadores externos (ORCID), nomes (instituições, cidades, estados, editoras, territórios), datas guardadas como texto e indicadores numéricos guardados como texto (JCR).

#### Scenario: ORCID fora da lista de valores
- **WHEN** o seed do Simcc roda e a fonte é sincronizada com poucos pesquisadores
- **THEN** a prévia mostra a coluna `orcid` sem listar valores

### Requirement: Relacionamentos na linha da coluna
Na prévia do contexto, cada relacionamento ligado entre entidades incluídas SHALL aparecer na linha da coluna de origem como `→ schema.entidade.coluna`, e a seção "Relacionamentos" MUST NOT aparecer. Um relacionamento com mais de uma coluna SHALL ser indicado na linha da primeira coluna, com todas as colunas das duas pontas.

#### Scenario: Chave estrangeira
- **WHEN** `bibliographic_production.researcher_id` referencia `researcher.id` e as duas entidades estão incluídas
- **THEN** a linha de `researcher_id` termina com `→ public.researcher.id` e não há seção "Relacionamentos"

#### Scenario: Ponta oculta
- **WHEN** a entidade de destino do relacionamento está oculta
- **THEN** a linha da coluna de origem não indica o relacionamento

## MODIFIED Requirements

### Requirement: Prévia do contexto do modelo
O sistema SHALL mostrar, por fonte, o texto que o modelo receberá sobre ela. A prévia SHALL incluir as instruções da fonte, as entidades visíveis e presentes (indicando as não consultáveis) e suas colunas visíveis e presentes, com tipo, descrição, valores listados, indicação de acesso `aggregate` e relacionamentos. A prévia MUST NOT incluir itens ocultos ou ausentes. Uma fonte desativada SHALL resultar em contexto vazio.

#### Scenario: Entidade oculta fora do contexto
- **WHEN** uma entidade está oculta
- **THEN** ela e suas colunas não aparecem na prévia

#### Scenario: Fonte desativada
- **WHEN** a fonte está desativada
- **THEN** a prévia é vazia e indica que a fonte está desativada

### Requirement: Valores observados no contexto do modelo
Para colunas com valores observados, sem enum e com a listagem permitida, a prévia do contexto SHALL listar todos os valores observados, com a descrição editorial quando houver, sob o rótulo "Valores", e MUST NOT listar valores obsoletos. A orientação de usar os valores exatamente como listados SHALL ficar nas regras do prompt, não em cada coluna.

#### Scenario: Valores reais no contexto
- **WHEN** `mv_bolsas_metricas.modalidade` tem valores observados e a listagem é permitida
- **THEN** a prévia lista `Doutorado - Cotas` e os demais valores da origem, sem `Doutorado`

#### Scenario: Sem valores observados nem enum
- **WHEN** a coluna não tem enum nem valores observados
- **THEN** a prévia lista os valores editoriais, como antes

### Requirement: Valores de enum no contexto do modelo
Para colunas com enum conhecido e `list_values` diferente de `never`, a prévia do contexto SHALL listar todos os valores atuais da origem, com a descrição editorial quando houver. Valores obsoletos MUST NOT aparecer no contexto.

#### Scenario: Valor sem descrição no contexto
- **WHEN** o enum tem um valor sem descrição
- **THEN** o valor aparece na prévia sem descrição, junto dos valores descritos

#### Scenario: Valor obsoleto fora do contexto
- **WHEN** um valor descrito deixou de existir no enum
- **THEN** ele não aparece na prévia
