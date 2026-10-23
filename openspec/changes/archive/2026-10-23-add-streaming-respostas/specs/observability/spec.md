# Spec Delta

## MODIFIED Requirements

### Requirement: Caminho da IA por resposta
Cada resposta da Maria, completa ou em streaming, SHALL gerar um span de cadeia `maria.chat` no padrão OpenInference, com entrada, saída e o identificador da conversa como sessão, contendo como filhos os spans das chamadas ao modelo, com mensagens, modelo e contagem de tokens.

#### Scenario: Inspeção de uma resposta
- **WHEN** a Maria responde a uma mensagem
- **THEN** existe um span `maria.chat` com `session.id` igual ao id da conversa e um span filho do LLM com as mensagens enviadas, a resposta e os tokens

#### Scenario: Falha do modelo rastreada
- **WHEN** o modelo falha durante a geração
- **THEN** o span `maria.chat` termina com status de erro e a exceção registrada

#### Scenario: Resposta em streaming rastreada
- **WHEN** a Maria responde pelo endpoint de streaming
- **THEN** o span `maria.chat` tem como saída o texto completo, e as métricas de tokens e duração são registradas como numa resposta completa
