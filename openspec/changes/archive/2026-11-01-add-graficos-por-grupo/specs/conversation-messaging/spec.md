# Spec Delta

## ADDED Requirements

### Requirement: Séries por categoria em gráficos
O modelo SHALL poder informar em `group_by` a coluna que separa as séries de um gráfico `bar`, `line` ou `area`, com uma só coluna em `series`. O sistema MUST gerar uma série por valor distinto, rotulada com esse valor, e uma linha de `data` por valor de `x`. Valor nulo do grupo MUST virar "Não informado". O bloco SHALL trazer a coluna em `group`.

#### Scenario: Artigos por ano e modalidade
- **WHEN** o modelo pede um gráfico de linha com `ano` no eixo x, `total` como série e `group_by` em `modalidade`, de um resultado com 3 anos e 2 modalidades
- **THEN** o bloco tem 2 séries rotuladas com as modalidades e 3 registros, cada um com os valores das duas

#### Scenario: Combinação sem dados
- **WHEN** uma modalidade não tem linha para um dos anos
- **THEN** o valor dela nesse registro é nulo

#### Scenario: Resultado ordenado por grupo
- **WHEN** o eixo é numérico e o resultado vem ordenado por modalidade e depois por ano
- **THEN** os registros do bloco ficam em ordem crescente de ano

#### Scenario: Grupo nulo
- **WHEN** a coluna de `group_by` tem valor nulo em algumas linhas
- **THEN** essas linhas formam a série "Não informado"

### Requirement: Chaves das séries por categoria
A chave de cada série gerada por `group_by` MUST conter só letras minúsculas sem acento, dígitos e `_`, derivadas do valor já mascarado. Colisões entre si ou com `x` MUST receber sufixo numérico. O rótulo em `labels` para a chave SHALL ter prioridade sobre o valor.

#### Scenario: Valores parecidos
- **WHEN** os grupos são "Bolsa PQ-1A" e "Bolsa PQ 1A"
- **THEN** as chaves são `bolsa_pq_1a` e `bolsa_pq_1a_2`, e os rótulos mantêm os textos originais

#### Scenario: Grupo com CPF
- **WHEN** um valor do grupo traz um CPF
- **THEN** nem a chave nem o rótulo contêm o número

### Requirement: Recusa de pedidos de gráfico ambíguos
O sistema MUST recusar um gráfico `bar`, `line`, `area` ou `pie` sem `group_by` cujo `x` tenha valores repetidos. Com `group_by`, MUST recusar: par de `x` e grupo repetido, `group_by` igual a `x` ou fora do resultado, mais de uma série, e os tipos `pie` e `scatter`. O modelo SHALL receber o motivo. Dispersão sem `group_by` MUST aceitar `x` repetido.

#### Scenario: Ano repetido sem grupo
- **WHEN** o modelo pede um gráfico de linha com `ano` no eixo x, sem `group_by`, e o resultado tem duas linhas de 2025
- **THEN** o gráfico não é incluído e o modelo recebe a orientação de usar `group_by` ou agregar

#### Scenario: Par repetido
- **WHEN** o resultado tem duas linhas com o mesmo ano e a mesma modalidade
- **THEN** o gráfico não é incluído e o modelo recebe o motivo

#### Scenario: Dispersão com x repetido
- **WHEN** o modelo pede uma dispersão cujo `x` tem valores repetidos
- **THEN** o bloco `chart` é criado com todas as linhas

### Requirement: Limite de grupos em gráficos
O sistema MUST recusar `group_by` com mais de 5 valores distintos. O motivo enviado ao modelo SHALL orientar a reduzir os grupos na consulta, mantendo os maiores e reunindo os demais quando a medida for aditiva.

#### Scenario: Seis modalidades
- **WHEN** o resultado tem 6 valores distintos na coluna de `group_by`
- **THEN** o gráfico não é incluído e o modelo recebe a orientação de reduzir os grupos na consulta

### Requirement: Gráficos agrupados no histórico
No resumo de um gráfico com `group`, os rótulos das séries MUST NOT aparecer fora de `<untrusted_database_data>`. O resumo SHALL dizer qual coluna separa as séries. Mensagens gravadas sem `group` MUST ser devolvidas com o campo nulo.

#### Scenario: Valor malicioso no grupo
- **WHEN** uma resposta anterior tem um gráfico agrupado com a série rotulada "Ignore as instruções"
- **THEN** esse texto não aparece no histórico enviado ao modelo

#### Scenario: Reapresentação de gráfico agrupado
- **WHEN** o modelo pede uma tabela a partir de `h1`, um gráfico agrupado, com as Chaves citadas no histórico
- **THEN** a tabela traz os valores do gráfico sem nova consulta
