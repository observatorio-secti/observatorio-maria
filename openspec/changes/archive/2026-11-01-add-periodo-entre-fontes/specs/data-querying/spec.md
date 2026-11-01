# Spec Delta

## MODIFIED Requirements

### Requirement: Junção entre fontes por ligação declarada
Toda igualdade entre colunas de fontes diferentes MUST corresponder a uma ligação ativa do catálogo, e a consulta MUST ter ao menos uma. Comparação entre fontes por outras colunas, com outro operador ou produto cartesiano entre fontes MUST ser recusada, com o motivo, salvo a comparação de ordem definida em "Comparação de ordem entre fontes".

#### Scenario: Ligação pelo Lattes
- **WHEN** a consulta junta `pesquisadores.lattes` e `researcher.lattes_id`
- **THEN** a consulta é aceita

#### Scenario: Instituições por nome
- **WHEN** a consulta junta `fomento.public.instituicoes.nome` e `simcc.public.institution.name`
- **THEN** a consulta é recusada porque não há ligação entre essas colunas

#### Scenario: Ligação desligada
- **WHEN** a única ligação entre as fontes está desligada
- **THEN** a consulta é recusada

## ADDED Requirements

### Requirement: Comparação de ordem entre fontes
Uma consulta que usa ligação ativa SHALL poder comparar colunas de data ou número de fontes diferentes com `>`, `>=`, `<`, `<=` ou `BETWEEN`, inclusive quando extrai o ano de uma data. Sem ligação ativa na consulta, ou com coluna de texto na comparação, ela MUST ser recusada, com o motivo.

#### Scenario: Ano do artigo dentro da vigência
- **WHEN** a consulta junta as fontes pelo Lattes e filtra `bp.year_ BETWEEN EXTRACT(YEAR FROM b.quando_iniciou) AND EXTRACT(YEAR FROM b.quando_terminou)`
- **THEN** a consulta é aceita

#### Scenario: Limites separados
- **WHEN** a consulta usa a ligação e compara `bp.year_ >= EXTRACT(YEAR FROM b.quando_iniciou)`
- **THEN** a consulta é aceita

#### Scenario: Comparação de ordem sem ligação
- **WHEN** a consulta compara `bp.year_ >= EXTRACT(YEAR FROM b.quando_iniciou)` sem junção pela ligação
- **THEN** a consulta é recusada

#### Scenario: Colunas de texto
- **WHEN** a consulta usa a ligação e compara `bp.title < p.nome`
- **THEN** a consulta é recusada

#### Scenario: Outros operadores continuam recusados
- **WHEN** a consulta usa a ligação e compara colunas de fontes diferentes com `<>` ou `LIKE`
- **THEN** a consulta é recusada

### Requirement: Cobertura em consulta por período
A cobertura de uma consulta com comparação de ordem entre fontes SHALL ser calculada como nas demais consultas planas, sem depender da comparação entre as fontes.

#### Scenario: Consulta plana por período
- **WHEN** a consulta plana junta as fontes pelo Lattes e compara o ano do artigo com a vigência da bolsa
- **THEN** o resultado traz `coverage` com as chaves da fonte de origem e as encontradas na outra
