# Spec Delta

## ADDED Requirements

### Requirement: Título do eixo Y nos gráficos
A página SHALL mostrar um título no eixo Y dos gráficos com eixos: o rótulo e a unidade da série, quando há uma só série, ou a unidade, quando todas as séries têm a mesma. Nos demais casos, o eixo Y MUST ficar sem título.

#### Scenario: Uma série
- **WHEN** um gráfico de barras tem uma série com rótulo "Bolsas" e unidade "un"
- **THEN** o eixo Y mostra "Bolsas (un)"

#### Scenario: Séries com a mesma unidade
- **WHEN** um gráfico de linhas tem duas séries com a unidade "R$"
- **THEN** o eixo Y mostra "R$"

#### Scenario: Séries com unidades diferentes
- **WHEN** um gráfico tem duas séries com unidades diferentes
- **THEN** o eixo Y fica sem título

#### Scenario: Gráfico de pizza
- **WHEN** a resposta tem um gráfico de pizza
- **THEN** o gráfico é mostrado sem eixos
