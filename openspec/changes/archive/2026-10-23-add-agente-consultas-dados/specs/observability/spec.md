# Spec Delta

## ADDED Requirements

### Requirement: Consultas rastreadas
Cada consulta pedida pelo modelo SHALL gerar um span de ferramenta no padrão OpenInference, filho de `maria.chat`, com a fonte, o SQL recebido, o resultado (linhas devolvidas e truncamento) ou o motivo da recusa. O conteúdo SQL e das linhas MUST seguir a mesma configuração de ocultação das mensagens.

#### Scenario: Consulta no trace
- **WHEN** a Maria executa duas consultas e responde
- **THEN** o span `maria.chat` tem como filhos as chamadas ao modelo e dois spans de ferramenta com o SQL e o número de linhas

#### Scenario: Conteúdo oculto
- **WHEN** a ocultação de conteúdo está ligada
- **THEN** os spans de ferramenta mantêm fonte, duração e status, sem o SQL nem as linhas

#### Scenario: Recusa rastreada
- **WHEN** uma consulta é recusada na validação
- **THEN** o span de ferramenta registra o motivo e não há span de banco na origem

### Requirement: Métricas do agente
O sistema SHALL registrar, por resposta, o número de chamadas ao modelo (`maria.agent.model_calls`) e, por consulta, o desfecho (`maria.query.count` com `outcome` igual a `executed`, `rejected`, `failed` ou `timeout`) e a fonte.

#### Scenario: Contagem por desfecho
- **WHEN** uma resposta tem uma consulta recusada e outra executada
- **THEN** `maria.query.count` registra uma ocorrência `rejected` e uma `executed`, e `maria.agent.model_calls` registra o número de chamadas da resposta
