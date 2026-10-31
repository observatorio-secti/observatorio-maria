# Spec Delta

## ADDED Requirements

### Requirement: Contador de perguntas restantes
Com uma conversa aberta e limite ligado, a página SHALL mostrar perto do campo de mensagem quantas perguntas restam e o limite, e SHALL atualizar o número ao fim de cada resposta. Sem conversa aberta ou com o limite desligado, o contador MUST ficar oculto.

#### Scenario: Conversa em andamento
- **WHEN** o usuário abre uma conversa com 3 perguntas gravadas e limite 10
- **THEN** a página mostra "Restam 7 de 10 perguntas"

#### Scenario: Depois de uma resposta
- **WHEN** a Maria termina de responder numa conversa que tinha 7 perguntas restantes
- **THEN** o contador passa a mostrar 6

#### Scenario: Limite desligado
- **WHEN** a API devolve `questions_limit` nulo
- **THEN** o contador não aparece

### Requirement: Aviso de fim das perguntas
Quando restar uma pergunta, o contador SHALL mudar para o destaque de aviso e informar que é a última. Sem perguntas restantes, SHALL orientar o uso de "+ Nova conversa". O número exibido MUST NOT ser negativo.

#### Scenario: Última pergunta
- **WHEN** a conversa tem 9 perguntas gravadas e limite 10
- **THEN** o contador em destaque informa que resta a última pergunta

#### Scenario: Limite atingido
- **WHEN** a conversa tem 10 perguntas gravadas e limite 10
- **THEN** o contador em destaque orienta o uso de "+ Nova conversa"

#### Scenario: Limite reduzido depois das perguntas
- **WHEN** a conversa tem 12 perguntas gravadas e o limite passou a 10
- **THEN** o contador mostra a mesma orientação de limite atingido
