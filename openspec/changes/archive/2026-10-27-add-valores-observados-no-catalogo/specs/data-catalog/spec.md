## ADDED Requirements

### Requirement: Leitura de valores observados
A sincronização e a verificação periódica SHALL ler os valores distintos das colunas de texto sem enum que estejam visíveis e presentes, em entidades consultáveis e com acesso `full`. A leitura MUST ser somente leitura, com limite de tempo, e MUST NOT tocar colunas ocultas, colunas `aggregate` ou entidades não consultáveis.

#### Scenario: Coluna categórica lida
- **WHEN** `mv_bolsas_metricas.modalidade` está visível, com acesso `full`, e a fonte é sincronizada
- **THEN** a coluna passa a expor os quatro valores existentes na origem, entre eles `Doutorado - Cotas`

#### Scenario: Coluna oculta não é lida
- **WHEN** uma coluna de texto está oculta
- **THEN** nenhum valor dela é lido da origem e seus valores observados ficam nulos

#### Scenario: Coluna somente para agregação não é lida
- **WHEN** uma coluna de texto visível tem acesso `aggregate`
- **THEN** nenhum valor dela é lido da origem

### Requirement: Limite de valores observados
Uma coluna SHALL ter valores observados apenas quando o número de valores distintos não nulos for no máximo `CATALOG_OBSERVED_VALUES_MAX` (padrão 50, mínimo 1). Acima disso, os valores observados MUST ficar nulos, e a coluna é tratada como texto livre. Valores nulos MUST NOT entrar na lista.

#### Scenario: Coluna de texto livre
- **WHEN** a coluna `pesquisadores.nome` tem milhares de valores distintos
- **THEN** seus valores observados ficam nulos

#### Scenario: Limite configurado
- **WHEN** `CATALOG_OBSERVED_VALUES_MAX` é 3 e a coluna tem 4 valores distintos
- **THEN** seus valores observados ficam nulos

### Requirement: Valores observados como dado técnico
Os valores observados SHALL ser guardados em campo técnico próprio, separado dos valores editoriais, e expostos pela API por coluna. Se a leitura de uma coluna falhar ou exceder o tempo, os valores anteriores SHALL ser mantidos e as demais colunas lidas. Os valores observados MUST NOT entrar na impressão digital do schema.

#### Scenario: Dados mudam sem defasagem
- **WHEN** a origem ganha um valor novo de `modalidade` sem mudar a estrutura
- **THEN** a verificação mantém a fonte `up_to_date` e atualiza os valores observados

#### Scenario: Falha numa coluna
- **WHEN** a leitura de uma coluna excede o tempo limite
- **THEN** os valores observados dela permanecem os da leitura anterior e as outras colunas são atualizadas

### Requirement: Pendentes e obsoletos com valores observados
Para colunas com valores observados e sem enum, a API SHALL tratar os valores observados como os valores atuais da origem: os sem descrição editorial SHALL aparecer como pendentes, e os valores editoriais ausentes da origem SHALL aparecer como obsoletos.

#### Scenario: Valor editorial que não existe na origem
- **WHEN** `bolsas.modalidade` tem o valor editorial `Doutorado` e a origem só tem `Doutorado - Cotas`
- **THEN** a API lista `Doutorado` como obsoleto e `Doutorado - Cotas` como sem descrição

### Requirement: Valores observados no contexto do modelo
Para colunas com valores observados e sem enum, a prévia do contexto SHALL listar todos os valores observados, com a descrição editorial quando houver, e MUST NOT listar valores obsoletos. O contexto SHALL indicar que os valores são os existentes na origem e devem ser usados como estão.

#### Scenario: Valores reais no contexto
- **WHEN** `mv_bolsas_metricas.modalidade` tem valores observados
- **THEN** a prévia lista `Doutorado - Cotas` e os demais valores da origem, sem `Doutorado`

#### Scenario: Sem valores observados nem enum
- **WHEN** a coluna não tem enum nem valores observados
- **THEN** a prévia lista os valores editoriais, como antes

### Requirement: Exemplos conferidos com o catálogo
Cada exemplo few-shot SHALL ser conferido com as mesmas regras de entidades, colunas e funções permitidas que valem para `query_data`. Exemplos que não passam MUST NOT entrar no contexto do modelo. A prévia do contexto SHALL listar os exemplos recusados, cada um com o motivo.

#### Scenario: Exemplo com coluna inexistente
- **WHEN** um exemplo usa `ano` em `mv_bolsas_metricas`, que só tem `ano_inicio`
- **THEN** o exemplo não aparece na seção few-shot e a prévia o lista como recusado, citando a coluna

#### Scenario: Exemplo válido
- **WHEN** todos os exemplos usam entidades e colunas visíveis e presentes
- **THEN** todos aparecem na seção few-shot e nenhum é listado como recusado

### Requirement: Seed do fomento sem valores supostos
O seed do fomento MUST NOT declarar valores para `bolsas.modalidade`, que passam a vir da origem. O exemplo de totais por ano SHALL usar `ano_inicio` em `mv_bolsas_metricas`.

#### Scenario: Seed em banco vazio
- **WHEN** o seed do fomento roda num banco vazio e a fonte é sincronizada
- **THEN** a prévia não contém exemplos recusados e `bolsas.modalidade` lista só os valores da origem
