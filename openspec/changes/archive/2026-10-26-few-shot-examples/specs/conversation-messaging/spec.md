# conversation-messaging Specification Delta

## Requirements

### MODIFIED Requirement: Contexto da conversa
Ao gerar uma resposta, o sistema SHALL enviar ao modelo as instruções de sistema da Maria, a data atual, o contexto de cada fonte consultável (o mesmo texto da prévia do catálogo, incluindo instruções, entidades, relacionamentos e exemplos few-shot cadastrados), o histórico da conversa em ordem cronológica e a nova mensagem do usuário. Blocos `chart` e `table` do histórico MUST ser enviados resumidos (título, colunas e número de linhas), sem os dados.

#### Scenario: Exemplos de consulta presentes no contexto enviado ao modelo
- **WHEN** a fonte `fomento` possui exemplos de consulta cadastrados e está ativa
- **THEN** o prompt de sistema entregue ao modelo contém os exemplos de pergunta e SQL sob a seção da fonte correspondente
