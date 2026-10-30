# Spec Delta

## ADDED Requirements

### Requirement: Explicação das visualizações
Quando todos os gráficos e tabelas pedidos numa chamada forem aceitos, o sistema SHALL fazer mais uma chamada ao modelo, sem ferramentas, para escrever a explicação, dentro do orçamento de chamadas. As instruções MUST pedir que a explicação diga o que a visualização mostra, o principal destaque e as ressalvas, usando só números dos resultados.

#### Scenario: Gráfico com explicação
- **WHEN** o modelo pede um gráfico sem escrever texto e ainda há chamada no orçamento
- **THEN** o modelo é chamado de novo sem ferramentas e a resposta tem o bloco `text` da explicação seguido do `chart`

#### Scenario: Tabela com explicação
- **WHEN** o modelo pede uma tabela sem escrever texto e ainda há chamada no orçamento
- **THEN** a resposta tem o bloco `text` da explicação seguido da `table`

#### Scenario: Instrução presente
- **WHEN** o modelo recebe as instruções de sistema com fontes consultáveis
- **THEN** elas pedem a explicação de cada visualização e orientam a não escrever texto na chamada que pede a visualização

### Requirement: Texto sem repetição entre chamadas
A chamada da explicação MUST orientar o modelo a não repetir o que já escreveu na resposta. Textos de chamadas diferentes SHALL ser separados por um parágrafo.

#### Scenario: Texto na chamada do gráfico
- **WHEN** o modelo escreve um texto na mesma chamada em que pede um gráfico e escreve a explicação na chamada seguinte
- **THEN** o bloco `text` tem os dois textos separados por uma linha em branco, e a chamada da explicação pede para não repetir o conteúdo

### Requirement: Visualização recusada
Quando um pedido de gráfico ou tabela for recusado e houver chamada restante, o modelo SHALL receber o motivo e MUST continuar com as ferramentas disponíveis, para corrigir o pedido.

#### Scenario: Correção do pedido
- **WHEN** o modelo pede um gráfico com uma coluna que não está no resultado e ainda há chamadas no orçamento
- **THEN** a chamada seguinte recebe o motivo, mantém as ferramentas e um novo pedido válido gera o `chart`

## MODIFIED Requirements

### Requirement: Última chamada sempre responde
A última chamada do orçamento MUST ser feita sem ferramentas, para que toda resposta termine com conteúdo ao usuário. Cada chamada SHALL informar ao modelo quantas chamadas ainda restam.

#### Scenario: Orçamento esgotado
- **WHEN** a segunda consulta falha e só resta uma chamada
- **THEN** a terceira chamada não pode consultar e o modelo responde com o que tem, dizendo o que não conseguiu obter

#### Scenario: Gráfico pedido antes da última chamada
- **WHEN** o modelo pede um gráfico na penúltima chamada do orçamento
- **THEN** a última chamada é feita sem ferramentas e a resposta tem a explicação seguida do `chart`

### Requirement: Ordem dos blocos da resposta
A resposta SHALL começar pelo bloco `text` da resposta final, seguido dos blocos `chart` e `table` na ordem em que foram pedidos. Uma resposta sem texto, só com gráficos e tabelas, MUST ser aceita como exceção, quando o modelo não devolver texto na chamada da explicação.

#### Scenario: Texto e gráfico
- **WHEN** o modelo pede um gráfico e uma tabela e depois escreve a explicação
- **THEN** `content` tem o bloco `text`, o `chart` e a `table`, nessa ordem

#### Scenario: Modelo sem texto na explicação
- **WHEN** o modelo não devolve texto na chamada da explicação
- **THEN** `content` tem só os blocos pedidos e a resposta é gravada normalmente
