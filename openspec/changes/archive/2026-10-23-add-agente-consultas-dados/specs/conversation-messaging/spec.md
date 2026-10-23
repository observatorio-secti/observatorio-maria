# Spec Delta

## MODIFIED Requirements

### Requirement: Contexto da conversa
Ao gerar uma resposta, o sistema SHALL enviar ao modelo as instruções de sistema da Maria, a data atual, o contexto de cada fonte consultável (o mesmo texto da prévia do catálogo), o histórico da conversa em ordem cronológica e a nova mensagem do usuário. Blocos `chart` e `table` do histórico MUST ser enviados resumidos (título, colunas e número de linhas), sem os dados.

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
- **WHEN** uma resposta anterior tem um bloco `chart` com 40 registros
- **THEN** o modelo recebe o título, as séries e o total de registros desse gráfico, sem os 40 registros

### Requirement: Envio com streaming
O sistema SHALL oferecer `POST /conversations/{id}/messages/stream`, com o mesmo corpo do envio comum, respondendo em Server-Sent Events na ordem: um `message.user`, zero ou mais `activity` e `content.delta` intercalados e um `message.assistant` com a mensagem persistida. Validação, conversa inexistente e indisponibilidade dos modelos MUST responder antes do stream, com os mesmos códigos HTTP do envio comum.

#### Scenario: Resposta transmitida em partes
- **WHEN** o cliente envia `{"content": "Oi"}` para o endpoint de streaming
- **THEN** recebe `message.user`, depois eventos `content.delta` cuja concatenação é o texto da resposta e, por fim, `message.assistant` com a resposta completa

#### Scenario: Mensagem final persistida
- **WHEN** o stream termina com `message.assistant`
- **THEN** o histórico da conversa contém a pergunta e a resposta, com os mesmos ids enviados nos eventos

#### Scenario: Conversa inexistente no streaming
- **WHEN** o cliente envia uma mensagem ao endpoint de streaming de uma conversa que não existe
- **THEN** o sistema responde 404 sem iniciar o stream

#### Scenario: Resposta com consulta
- **WHEN** a Maria consulta o fomento antes de responder
- **THEN** o cliente recebe `message.user`, um ou mais `activity`, os `content.delta` da resposta e `message.assistant`

## ADDED Requirements

### Requirement: Respostas com consulta a dados
Quando houver fontes consultáveis, o modelo SHALL poder consultá-las antes de responder, conforme a capacidade `data-querying`. Sem fontes consultáveis, a resposta SHALL ser gerada como antes, sem consultas.

#### Scenario: Pergunta sobre o fomento
- **WHEN** o usuário pergunta "Existe fomento na temática de dengue entre 2024 e 2026? Quais projetos?" e o fomento está ativo
- **THEN** a resposta se baseia em consultas ao fomento que buscam o tema em título, resumo ou palavras-chave e no período pedido

#### Scenario: Sem fontes
- **WHEN** nenhuma fonte está ativa
- **THEN** a Maria responde com uma única chamada ao modelo, sem consultas

### Requirement: Orçamento de chamadas por resposta
Cada resposta SHALL usar no máximo `MARIA_AGENT_MAX_MODEL_CALLS` chamadas ao modelo (padrão 3, mínimo 1), contando a que produz a resposta final. Valores menores que 1 MUST impedir a inicialização da aplicação.

#### Scenario: Orçamento respeitado
- **WHEN** o modelo pede uma nova consulta em todas as chamadas
- **THEN** a resposta é concluída com exatamente 3 chamadas ao modelo

### Requirement: Última chamada sempre responde
A última chamada do orçamento MUST ser feita sem a possibilidade de novas consultas, para que toda resposta termine com conteúdo ao usuário. Cada chamada SHALL informar ao modelo quantas chamadas ainda restam.

#### Scenario: Orçamento esgotado
- **WHEN** a segunda consulta falha e só resta uma chamada
- **THEN** a terceira chamada não pode consultar e o modelo responde com o que tem, dizendo o que não conseguiu obter

### Requirement: Gráficos a partir de resultados
O modelo SHALL poder pedir um bloco `chart` indicando o resultado de uma consulta, o tipo, o título, a coluna do eixo `x` e as colunas das séries. O sistema MUST preencher `data` com as linhas do resultado, e MUST recusar colunas que não existam nele.

#### Scenario: Gráfico de bolsas por ano
- **WHEN** o modelo pede um gráfico de barras com `ano_inicio` no eixo x e `quantidade` como série, a partir de um resultado com 3 anos
- **THEN** a resposta contém um bloco `chart` com 3 registros cujos valores são exatamente os do resultado

#### Scenario: Coluna inexistente
- **WHEN** o modelo pede uma série com uma coluna que não está no resultado
- **THEN** o gráfico não é incluído e, se houver chamada restante, o modelo recebe o motivo

### Requirement: Tabelas a partir de resultados
O modelo SHALL poder pedir um bloco `table` indicando o resultado, um título opcional e as colunas a exibir com seus rótulos. O sistema MUST preencher `rows` com as linhas do resultado e MUST recusar colunas que não existam nele.

#### Scenario: Lista de projetos
- **WHEN** o modelo pede uma tabela com as colunas `nome` e `ano` de um resultado com 12 projetos
- **THEN** a resposta contém um bloco `table` com 12 linhas e apenas essas duas colunas

### Requirement: Ordem dos blocos da resposta
A resposta SHALL começar pelo bloco `text` da resposta final, seguido dos blocos `chart` e `table` na ordem em que foram pedidos. Uma resposta sem texto, só com gráficos e tabelas, MUST ser aceita.

#### Scenario: Texto e gráfico
- **WHEN** o modelo responde com um texto e pede um gráfico e uma tabela
- **THEN** `content` tem o bloco `text`, o `chart` e a `table`, nessa ordem

### Requirement: Resposta parcial
Quando parte da pergunta depender de dados que nenhuma fonte consultável tem, a resposta SHALL responder a parte possível e MUST dizer explicitamente o que não pôde ser respondido e por quê, sem inventar dados para essa parte.

#### Scenario: Artigos ainda indisponíveis
- **WHEN** o usuário pergunta pelo fomento sobre dengue e pelos artigos produzidos, e nenhuma fonte tem artigos
- **THEN** a resposta traz o resultado do fomento e diz que os artigos ainda não estão disponíveis para consulta

#### Scenario: Critério ausente nos dados
- **WHEN** a pergunta filtra por um critério que não existe nas fontes consultáveis
- **THEN** a resposta diz que esse critério não pôde ser aplicado

### Requirement: Blocos de dados no streaming
Blocos `chart` e `table` SHALL ser enviados inteiros, cada um num único `content.delta` com `index`, `type` e o campo `block` contendo o bloco completo, depois do texto da resposta.

#### Scenario: Gráfico transmitido
- **WHEN** a resposta tem um texto e um gráfico
- **THEN** o cliente recebe os `content.delta` do texto com `index` 0 e um `content.delta` com `index` 1, `type` `chart` e o bloco completo em `block`

### Requirement: Evento de atividade
Antes de cada consulta, o streaming SHALL enviar um evento `activity` com `kind` igual a `query`, o nome da fonte e uma descrição curta, em português, do que está sendo consultado. O evento MUST NOT conter SQL, nomes de modelo, níveis ou URLs.

#### Scenario: Consulta anunciada
- **WHEN** o modelo consulta projetos sobre dengue no fomento
- **THEN** o cliente recebe `activity` com `kind` `query`, a fonte "Fomento à pesquisa" e uma descrição como "Buscando projetos sobre dengue"
