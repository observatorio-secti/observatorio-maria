## ADDED Requirements

### Requirement: Impressão digital do schema
Cada sincronização bem-sucedida SHALL registrar na fonte uma impressão digital da estrutura lida: entidades e tipos, colunas com tipo, nulabilidade e chave primária, chaves estrangeiras e valores de enum. A ordem de leitura MUST NOT alterar a impressão digital.

#### Scenario: Sincronização registra a impressão digital
- **WHEN** uma fonte é sincronizada
- **THEN** a fonte fica com estado `up_to_date` e sem defasagem registrada

### Requirement: Verificação de defasagem
O sistema SHALL verificar uma fonte sob demanda, lendo o schema atual da origem em modo somente leitura e comparando-o com a impressão digital da última sincronização, sem alterar o catálogo editorial. O estado da fonte SHALL ser um entre `unknown` (nunca verificada nem sincronizada), `up_to_date`, `outdated` e `error`. A fonte SHALL guardar a data da última verificação.

#### Scenario: Schema inalterado
- **WHEN** a origem não mudou desde a sincronização e a fonte é verificada
- **THEN** o estado é `up_to_date` e não há diff

#### Scenario: Schema alterado
- **WHEN** uma coluna foi adicionada na origem e a fonte é verificada
- **THEN** o estado é `outdated` e o catálogo continua sem a coluna

#### Scenario: Origem inacessível na verificação
- **WHEN** a verificação não consegue ler a origem
- **THEN** o estado é `error`, a mensagem fica registrada na fonte sem a URL de conexão e o catálogo não muda

### Requirement: Diff da defasagem
Uma fonte `outdated` SHALL expor o que mudou em relação ao catálogo: entidades e colunas novas e ausentes, colunas com tipo, nulabilidade ou chave primária alterados, valores de enum novos e removidos e a quantidade de relacionamentos novos e ausentes. O diff SHALL corresponder ao que a sincronização seguinte aplicaria.

#### Scenario: Diff de coluna removida e enum novo
- **WHEN** uma coluna catalogada foi removida e um enum ganhou um valor
- **THEN** o diff lista a coluna como ausente e o valor como novo

### Requirement: Verificação periódica
O sistema SHALL verificar todas as fontes ativas ao iniciar e depois no intervalo definido por `CATALOG_CHECK_INTERVAL_SECONDS` (padrão 3600). O valor `0` SHALL desligar a verificação periódica. Fontes desativadas MUST NOT ser verificadas. A falha numa fonte MUST NOT impedir a verificação das demais nem os ciclos seguintes.

#### Scenario: Uma fonte falha
- **WHEN** um ciclo verifica duas fontes e a primeira está inacessível
- **THEN** a primeira fica em `error` e a segunda é verificada normalmente

#### Scenario: Fonte desativada
- **WHEN** um ciclo roda com uma fonte desativada
- **THEN** a fonte desativada não é verificada

### Requirement: Sincronização automática
Cada fonte SHALL ter o interruptor `auto_sync`, desligado por padrão e configurável pela API e pelo YAML. Quando ligado, uma verificação que detecte defasagem SHALL sincronizar a fonte imediatamente, com as mesmas regras da sincronização manual, e a resposta SHALL incluir o resumo da sincronização.

#### Scenario: Defasagem com sincronização automática
- **WHEN** uma fonte com `auto_sync` ligado é verificada após uma tabela nova surgir na origem
- **THEN** a tabela entra no catálogo oculta e o estado é `up_to_date`

#### Scenario: Defasagem sem sincronização automática
- **WHEN** a mesma situação ocorre com `auto_sync` desligado
- **THEN** o estado é `outdated` e a tabela não entra no catálogo

### Requirement: Valores de enum
A sincronização SHALL ler os valores dos tipos enum nativos da origem para cada coluna. A API SHALL expor, por coluna, os valores atuais da origem, os valores sem descrição editorial e os valores descritos que não existem mais na origem (obsoletos). A sincronização SHALL relatar os valores novos em colunas cujo enum já era conhecido.

#### Scenario: Valor novo no enum
- **WHEN** o enum de `status` ganha o valor `SUSPENSA` e a fonte é sincronizada
- **THEN** o relatório lista o valor novo e a coluna o expõe como sem descrição

### Requirement: Valores de enum no contexto do modelo
Para colunas com enum conhecido, a prévia do contexto SHALL listar todos os valores atuais da origem, com a descrição editorial quando houver. Valores obsoletos MUST NOT aparecer no contexto.

#### Scenario: Valor sem descrição no contexto
- **WHEN** o enum tem um valor sem descrição
- **THEN** o valor aparece na prévia sem descrição, junto dos valores descritos

#### Scenario: Valor obsoleto fora do contexto
- **WHEN** um valor descrito deixou de existir no enum
- **THEN** ele não aparece na prévia
