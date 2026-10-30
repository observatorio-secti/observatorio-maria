# Spec Delta

## ADDED Requirements

### Requirement: Texto intercalado com os blocos
O modelo SHALL poder marcar no texto a posição de um gráfico ou tabela com `[[bloco:N]]`, em que N é o `block_index` devolvido pela ferramenta. O sistema MUST dividir o texto em blocos `text` e colocar o bloco citado nessa posição. O marcador MUST NOT aparecer para o cliente.

#### Scenario: Dois gráficos com explicação própria
- **WHEN** o texto final é `Primeiro. [[bloco:1]] Segundo. [[bloco:2]]`
- **THEN** `content` tem `text`, `chart`, `text` e `chart`, nessa ordem, sem os marcadores

#### Scenario: Bloco não citado
- **WHEN** o modelo pede dois gráficos e cita só o segundo
- **THEN** o segundo aparece na posição citada, e o primeiro vem depois do texto

### Requirement: Marcadores inválidos
Marcador de um bloco inexistente ou já colocado MUST ser removido, sem erro e sem repetir o bloco. Blocos `text` vazios depois da divisão MUST ficar de fora da resposta.

#### Scenario: Bloco inexistente
- **WHEN** o texto cita `[[bloco:9]]` e a resposta tem um gráfico
- **THEN** o marcador some e o gráfico vem depois do texto

#### Scenario: Marcador repetido
- **WHEN** o texto cita `[[bloco:1]]` duas vezes
- **THEN** o gráfico aparece uma vez, na primeira posição

### Requirement: Marcadores no streaming
No streaming, o sistema MUST reter o texto que possa ser o início de um marcador até decidir, e SHALL emitir cada bloco citado na sua posição, com `index` crescente. Ao fim, o texto retido que não formou um marcador MUST ser emitido.

#### Scenario: Marcador dividido entre fragmentos
- **WHEN** o marcador chega dividido em `[[blo` e `co:1]]`
- **THEN** nenhum delta contém parte do marcador, e o bloco é emitido nessa posição

#### Scenario: Colchetes comuns
- **WHEN** o texto termina com `[1`
- **THEN** esse texto é emitido normalmente ao fim

## MODIFIED Requirements

### Requirement: Ordem dos blocos da resposta
A resposta SHALL seguir a ordem definida pelos marcadores de posição do texto. Sem marcadores, ela SHALL começar pelo bloco `text`, seguido dos blocos `chart` e `table` na ordem em que foram pedidos. Blocos não citados SHALL vir depois do texto, nessa mesma ordem. Uma resposta sem texto, só com gráficos e tabelas, MUST ser aceita como exceção, quando o modelo não devolver texto na chamada da explicação.

#### Scenario: Texto e gráfico
- **WHEN** o modelo pede um gráfico e uma tabela e depois escreve a explicação
- **THEN** `content` tem o bloco `text`, o `chart` e a `table`, nessa ordem

#### Scenario: Modelo sem texto na explicação
- **WHEN** o modelo não devolve texto na chamada da explicação
- **THEN** `content` tem só os blocos pedidos e a resposta é gravada normalmente
