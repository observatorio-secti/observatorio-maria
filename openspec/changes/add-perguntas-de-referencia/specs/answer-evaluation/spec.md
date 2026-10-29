# Spec Delta

## Purpose
Mede a precisão das respostas da Maria com o modelo real, contra perguntas de referência versionadas, para que mudanças no contexto enviado ao modelo possam ser comparadas com uma linha de base.

## ADDED Requirements

### Requirement: Perguntas de referência versionadas
O repositório SHALL manter um arquivo de perguntas de referência em que cada pergunta tem um identificador único, o texto, as fontes que a resposta deve consultar, um ou mais critérios de acerto e as consultas de conferência que produziram a resposta esperada.

#### Scenario: Arquivo válido carregado
- **WHEN** a avaliação carrega o arquivo de perguntas de referência
- **THEN** cada pergunta fica disponível com identificador, texto, fontes esperadas, critérios e consultas de conferência

#### Scenario: Arquivo inválido recusado
- **WHEN** o arquivo tem identificador repetido, critério de tipo desconhecido ou pergunta sem critério
- **THEN** a avaliação termina com erro antes de chamar o modelo, indicando a pergunta e o problema

### Requirement: Execução com o modelo real fora da suíte de testes
Um comando próprio, separado da suíte de testes, SHALL enviar cada pergunta de referência numa conversa nova, pelo mesmo fluxo de geração da API, com o modelo e as fontes configurados. A suíte de testes continua sem chamar modelos reais.

#### Scenario: Avaliação completa
- **WHEN** o comando de avaliação é executado sem filtros
- **THEN** cada pergunta de referência é respondida pela Maria em uma conversa própria e avaliada

#### Scenario: Filtro por pergunta
- **WHEN** o comando é executado com o identificador de uma ou mais perguntas
- **THEN** só essas perguntas são executadas

#### Scenario: Banco da Maria preservado
- **WHEN** a avaliação termina
- **THEN** nenhuma conversa ou mensagem da avaliação fica gravada no banco da Maria configurado

### Requirement: Critério numérico
Um critério numérico SHALL passar quando o valor esperado aparece na resposta, em texto ou nas células de tabela, aceitando a formatação brasileira de milhares e decimais.

#### Scenario: Número com separador de milhar
- **WHEN** o valor esperado é 3653 e a resposta diz "3.653 bolsistas"
- **THEN** o critério passa

#### Scenario: Número ausente
- **WHEN** o valor esperado é 20 e nenhum texto ou célula da resposta contém 20
- **THEN** o critério falha e o relatório mostra o valor esperado

### Requirement: Critério de lista
Um critério de lista SHALL passar quando a fração dos itens esperados encontrados na resposta atinge o mínimo definido na pergunta (padrão 100%), comparando sem diferença de maiúsculas, acentos e espaços.

#### Scenario: Lista completa
- **WHEN** a pergunta espera 20 títulos e a resposta contém os 20
- **THEN** o critério passa

#### Scenario: Lista incompleta
- **WHEN** a pergunta espera 20 títulos com mínimo de 90% e a resposta contém 15
- **THEN** o critério falha e o relatório mostra quantos itens foram encontrados

### Requirement: Critério de fonte consultada
Um critério de fonte SHALL passar quando as fontes consultadas com sucesso pela Maria incluem todas as fontes exigidas e nenhuma das fontes proibidas pela pergunta.

#### Scenario: Fonte certa
- **WHEN** a pergunta exige `simcc` e a Maria consulta só o `simcc`
- **THEN** o critério passa

#### Scenario: Fonte proibida
- **WHEN** a pergunta exige `fomento`, proíbe `simcc` e a Maria consulta as duas
- **THEN** o critério falha e o relatório lista as fontes consultadas

### Requirement: Critério textual avaliado por modelo-juiz
Um critério textual SHALL ser avaliado por um modelo-juiz, que recebe a pergunta, a resposta e a descrição do critério e devolve aprovado ou reprovado com uma justificativa curta. O juiz é usado só nesse tipo de critério.

#### Scenario: Limite declarado
- **WHEN** o critério é "declara que não é possível agregar todos os bolsistas" e a resposta explica esse limite
- **THEN** o juiz aprova e a justificativa entra no relatório

#### Scenario: Juiz indisponível
- **WHEN** o modelo-juiz falha
- **THEN** o critério fica como erro, sem contar como acerto, e as demais perguntas continuam

### Requirement: Resultado por pergunta
Uma pergunta SHALL ser considerada certa só quando todos os seus critérios passam. Falha do modelo ou da consulta durante a resposta SHALL contar como erro da pergunta, sem interromper as demais.

#### Scenario: Um critério falha
- **WHEN** o critério de fonte passa e o numérico falha
- **THEN** a pergunta é marcada como errada

#### Scenario: Falha do modelo
- **WHEN** o modelo falha ao responder uma pergunta
- **THEN** a pergunta é marcada como erro e a avaliação segue para a próxima

### Requirement: Relatório da avaliação
Ao final, a avaliação SHALL mostrar por pergunta o resultado, cada critério, os tokens, as chamadas ao modelo e as consultas feitas, além do total de acertos. SHALL também gravar o relatório em JSON com data, modelo usado e respostas, fora do controle de versão.

#### Scenario: Relatório gerado
- **WHEN** a avaliação de 6 perguntas termina com 4 acertos
- **THEN** o terminal mostra "4/6" e os detalhes por pergunta, e um arquivo JSON com os mesmos dados é gravado

#### Scenario: Relatório sem segredos
- **WHEN** o relatório é gravado
- **THEN** ele não contém URLs de conexão nem credenciais

### Requirement: Repetições
O comando SHALL aceitar um número de repetições por pergunta e informar a taxa de acerto de cada pergunta entre as repetições.

#### Scenario: Três repetições
- **WHEN** a avaliação roda com 3 repetições e uma pergunta acerta em 2
- **THEN** o relatório mostra 2/3 para essa pergunta

### Requirement: Conferência das respostas esperadas
Um modo de conferência SHALL executar as consultas de conferência de cada pergunta nas fontes, somente leitura e sem chamar o modelo, e apontar as perguntas cuja resposta esperada difere do resultado atual.

#### Scenario: Resposta esperada desatualizada
- **WHEN** a consulta de conferência devolve 31 e a resposta esperada é 29
- **THEN** a conferência aponta a pergunta, o valor esperado e o valor atual, sem alterar o arquivo

#### Scenario: Conferência em duas etapas
- **WHEN** a conferência de uma pergunta entre fontes consulta o fomento e usa os Lattes obtidos para filtrar o Simcc
- **THEN** a segunda consulta recebe os valores da primeira e o resultado final é comparado com a resposta esperada
