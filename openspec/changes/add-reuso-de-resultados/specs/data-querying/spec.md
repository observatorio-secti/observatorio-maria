# Spec Delta

## ADDED Requirements

### Requirement: Resultados restaurados de blocos anteriores
No início de cada resposta, gráficos e tabelas das mensagens anteriores da conversa SHALL ficar disponíveis como resultados com identificadores `h1`, `h2`…, em ordem cronológica, com as colunas e linhas gravadas no bloco. Isso MUST NOT abrir conexão com as origens.

#### Scenario: Gráfico anterior disponível
- **WHEN** a conversa tem uma resposta anterior com um gráfico de `ano` e `total`
- **THEN** o modelo pode pedir um novo bloco com o resultado `h1`, usando essas colunas, sem consulta

#### Scenario: Coluna que não está no bloco anterior
- **WHEN** o modelo pede `h1` com uma coluna que não foi gravada no bloco
- **THEN** o pedido é recusado com o motivo, como em qualquer resultado

#### Scenario: Identificador inexistente
- **WHEN** o modelo pede o resultado `h9` e a conversa não tem esse bloco
- **THEN** o pedido é recusado com o motivo
