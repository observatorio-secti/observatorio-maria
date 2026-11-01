# Spec Delta

## ADDED Requirements

### Requirement: Barras horizontais na página
A página SHALL desenhar gráficos com `orientation` igual a `horizontal` com as categorias no eixo vertical e os valores no eixo horizontal, que recebe o título de valores. A altura SHALL crescer com o número de categorias, para que todos os rótulos fiquem legíveis, sem rolagem horizontal da página a 375px.

#### Scenario: Muitos territórios
- **WHEN** a resposta tem um gráfico horizontal com 27 territórios
- **THEN** os 27 rótulos aparecem sem sobreposição, inclusive a 375px

#### Scenario: Título dos valores
- **WHEN** um gráfico horizontal tem uma série com rótulo "Pesquisadores"
- **THEN** o título "Pesquisadores" aparece no eixo horizontal

### Requirement: Barras empilhadas na página
A página SHALL desenhar gráficos com `stacking` como barras empilhadas, na vertical ou na horizontal. Com `percent`, SHALL mostrar cada barra como 100%, com eixo em porcentagem, e tratar valor nulo como zero na proporção. O detalhe de cada segmento SHALL mostrar a porcentagem e o valor absoluto.

#### Scenario: Empilhamento 100%
- **WHEN** a resposta tem um gráfico com `stacking` igual a `percent` e valores 30 e 10 no mesmo `x`
- **THEN** os segmentos ocupam 75% e 25%, e o detalhe mostra também 30 e 10

#### Scenario: Conversa reaberta
- **WHEN** o usuário reabre uma conversa com um gráfico empilhado
- **THEN** o gráfico é desenhado da mesma forma que no streaming

### Requirement: Rosca na página
A página SHALL desenhar blocos `donut` como rosca, sem eixos, com uma cor por fatia.

#### Scenario: Rosca sem eixos
- **WHEN** a resposta tem um gráfico `donut`
- **THEN** ele é mostrado como rosca, sem eixos

### Requirement: Exportação dos novos formatos
O PNG SHALL reproduzir a orientação, o empilhamento e a altura vistos na tela. O CSV SHALL trazer sempre os valores absolutos de `data`.

#### Scenario: PNG de gráfico horizontal
- **WHEN** o usuário baixa o PNG de um gráfico horizontal com 27 territórios
- **THEN** o arquivo mostra os 27 rótulos

#### Scenario: CSV de gráfico 100%
- **WHEN** o usuário baixa o CSV de um gráfico com `stacking` igual a `percent`
- **THEN** o arquivo traz os valores absolutos, e não as porcentagens

### Requirement: Novos formatos no contrato de blocos
A aba de contrato da página SHALL incluir um exemplo de gráfico de barras horizontal e empilhado, com o JSON correspondente, além dos blocos que já mostra.

#### Scenario: Exemplo no contrato
- **WHEN** o usuário abre a aba de contrato
- **THEN** vê o gráfico de exemplo renderizado ao lado do JSON com `orientation` e `stacking`
