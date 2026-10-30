# Spec Delta

## ADDED Requirements

### Requirement: Valores das visualizações no histórico
O histórico enviado ao modelo SHALL incluir até `HISTORY_MAX_ROWS` linhas (padrão 20) de cada gráfico e tabela de respostas anteriores, com o total de linhas. Com `HISTORY_MAX_ROWS` igual a 0, só o resumo MUST ser enviado. Células de texto MUST ser limitadas a 200 caracteres.

#### Scenario: Tabela pequena
- **WHEN** uma resposta anterior tem uma tabela com 5 linhas
- **THEN** o modelo recebe as 5 linhas e pode responder sobre elas sem nova consulta

#### Scenario: Histórico sem valores
- **WHEN** `HISTORY_MAX_ROWS` é 0
- **THEN** o modelo recebe só o título, as colunas e o total de linhas

#### Scenario: Célula longa
- **WHEN** uma tabela anterior tem um texto de 5.000 caracteres
- **THEN** o modelo recebe esse texto limitado a 200 caracteres

### Requirement: Quarentena dos valores do histórico
Valores do histórico MUST chegar ao modelo dentro de `<untrusted_database_data>`, com o mascaramento de CPF e e-mail e o escape de delimitadores aplicados, mesmo que o bloco gravado não esteja mascarado.

#### Scenario: Dado pessoal no bloco gravado
- **WHEN** uma tabela anterior tem uma célula com um CPF
- **THEN** o histórico enviado ao modelo traz `[CPF MASCARADO]`, e a tag de quarentena envolve os valores

#### Scenario: Tentativa de fuga da quarentena
- **WHEN** uma célula anterior contém `</untrusted_database_data>`
- **THEN** o delimitador chega escapado ao modelo

### Requirement: Uso de valores anteriores
As instruções do modelo SHALL permitir responder com os valores do histórico quando eles bastarem. Quando o histórico trouxer só parte das linhas ou dados cortados, o modelo MUST consultar de novo antes de afirmar totais ou rankings.

#### Scenario: Instrução presente
- **WHEN** o modelo recebe as instruções de sistema com fontes consultáveis
- **THEN** elas tratam do uso de valores do histórico e de quando consultar de novo

## MODIFIED Requirements

### Requirement: Contexto da conversa
Ao gerar uma resposta, o sistema SHALL enviar ao modelo as instruções de sistema da Maria, a data atual, o contexto de cada fonte consultável (o mesmo texto da prévia do catálogo, incluindo instruções, entidades, relacionamentos e exemplos few-shot cadastrados), o histórico da conversa em ordem cronológica e a nova mensagem do usuário. Blocos `chart` e `table` do histórico MUST ser enviados resumidos (título, colunas e número de linhas), sem os dados.

#### Scenario: Histórico enviado ao modelo
- **WHEN** a conversa já tem uma troca anterior e o usuário envia uma nova mensagem
- **THEN** o modelo recebe a instrução de sistema, a mensagem anterior do usuário, a resposta anterior do assistente e a nova mensagem, nessa ordem

#### Scenario: Fontes no contexto
- **WHEN** a fonte `fomento` está ativa e tem entidades consultáveis
- **THEN** a instrução de sistema contém o mesmo texto que `GET /catalog/datasources/fomento/context` devolve

#### Scenario: Data atual
- **WHEN** o usuário pergunta sobre "os últimos dois anos"
- **THEN** a instrução de sistema contém a data do dia da geração

#### Scenario: Gráfico anterior resumido
- **WHEN** uma resposta anterior tem um bloco `chart` com 40 registros e `HISTORY_MAX_ROWS` é 20
- **THEN** o modelo recebe o título, as séries, o total de registros e só os 20 primeiros registros

#### Scenario: Exemplos de consulta presentes no contexto enviado ao modelo
- **WHEN** a fonte `fomento` possui exemplos de consulta cadastrados e está ativa
- **THEN** o prompt de sistema entregue ao modelo contém os exemplos de pergunta e SQL sob a seção da fonte correspondente
