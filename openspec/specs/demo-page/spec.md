# demo-page Specification

## Purpose
Página de demonstração servida pela própria API que permite conversar com a Maria e visualizar o contrato de blocos, para apresentar o sistema a usuários e à gestão.

## Requirements

### Requirement: Página montada na API
O sistema SHALL servir a página de demonstração em `/demo/` quando `DEMO_ENABLED` for verdadeiro (padrão) e MUST NOT servi-la quando for falso.

#### Scenario: Demo habilitada
- **WHEN** o usuário acessa `/demo/` com a demo habilitada
- **THEN** a página é exibida

#### Scenario: Demo desabilitada
- **WHEN** a aplicação inicia com `DEMO_ENABLED=false` e o usuário acessa `/demo/`
- **THEN** o sistema responde 404

### Requirement: Envio imediato de mensagens
A página SHALL permitir digitar e enviar uma mensagem assim que é aberta. Sem conversa selecionada, o envio MUST criar uma conversa e enviar a mensagem nela.

#### Scenario: Primeira mensagem sem conversa
- **WHEN** o usuário abre a página, digita uma pergunta e envia
- **THEN** uma conversa é criada, aparece na lista com o título da pergunta e exibe a resposta da Maria

### Requirement: Feedback durante a geração
Enquanto aguarda a resposta, a página SHALL indicar que a Maria está respondendo até o primeiro fragmento chegar e, a partir daí, SHALL exibir o texto progressivamente, renderizado em Markdown. A página MUST impedir envios duplicados até o fim da resposta. Caso a API retorne HTTP 429 por teto de tokens da conversa excedido, a página MUST exibir banner com mensagem explicativa e orientação para criar uma nova conversa.

#### Scenario: Aguardando resposta
- **WHEN** o usuário envia uma mensagem
- **THEN** a página mostra um indicador de resposta em andamento até o primeiro fragmento chegar ou um erro ser exibido

#### Scenario: Texto aparecendo
- **WHEN** a Maria gera a resposta
- **THEN** o texto aparece na mensagem do assistente à medida que é gerado e, ao final, a mensagem exibe o horário da versão persistida

#### Scenario: Banner de limite de tokens
- **WHEN** o usuário tenta enviar mensagem para conversa com cota de tokens esgotada
- **THEN** a página exibe banner informando que o teto de tokens da conversa foi atingido e orientando a iniciar uma nova conversa

### Requirement: Gestão de conversas na página
A página SHALL listar as conversas e permitir criar, abrir, renomear e excluir conversas.

#### Scenario: Renomear e excluir
- **WHEN** o usuário renomeia e depois exclui uma conversa
- **THEN** a lista reflete o novo título e, em seguida, a remoção

### Requirement: Demonstração do contrato de blocos
A página SHALL exibir uma resposta de exemplo com blocos `text`, `chart` e `table` renderizados, um bloco de tipo desconhecido ignorado e o JSON correspondente.

#### Scenario: Aba de contrato
- **WHEN** o usuário abre a aba de contrato de blocos
- **THEN** vê o texto, o gráfico e a tabela renderizados ao lado do JSON

### Requirement: Sem detalhes internos
A página MUST NOT exibir níveis de modelo, nomes de modelos ou listagem de endpoints.

#### Scenario: Interface limpa
- **WHEN** o usuário navega pela página
- **THEN** não há seletor de nível, nome de modelo nem aba de endpoints

### Requirement: Configuração do catálogo de dados na página
A página SHALL ter uma aba "Catálogo de dados" que permita escolher uma fonte, sincronizá-la, ativá-la ou desativá-la e editar suas instruções. Erros da API, como origem inacessível, SHALL ser exibidos na aba.

#### Scenario: Sincronizar
- **WHEN** o usuário clica em sincronizar
- **THEN** a aba mostra o resumo do que foi adicionado e do que ficou ausente e atualiza a lista de entidades

#### Scenario: Origem inacessível
- **WHEN** a sincronização falha porque a origem está fora do ar
- **THEN** a aba exibe a mensagem de erro e mantém o catálogo exibido

### Requirement: Edição de entidades e colunas na página
A aba SHALL listar as entidades com indicação de presença e permitir alternar **visível** e **consultável** e editar rótulo, descrição e sinônimos. Para a entidade selecionada, SHALL permitir alternar a visibilidade, alterar o acesso e editar a descrição de cada coluna.

#### Scenario: Ocultar uma tabela
- **WHEN** o usuário desliga "visível" de uma entidade na aba
- **THEN** a entidade aparece como oculta e some da prévia do contexto

#### Scenario: Coluna somente agregação
- **WHEN** o usuário muda o acesso de uma coluna para `aggregate`
- **THEN** a prévia passa a marcar a coluna como somente agregação

### Requirement: Relacionamentos, prévia e exportação na página
A aba SHALL listar e permitir ligar e desligar os relacionamentos, exibir a prévia do contexto que o modelo receberá e baixar o YAML exportado.

#### Scenario: Ver o que o modelo enxerga
- **WHEN** o usuário abre a prévia do contexto
- **THEN** vê o texto que o modelo receberá, apenas com itens visíveis e presentes

### Requirement: Estado do schema na página
A aba do catálogo SHALL exibir o estado do schema da fonte e a data da última verificação, permitir verificar sob demanda e ligar ou desligar a sincronização automática. Quando a fonte estiver desatualizada, SHALL exibir as mudanças detectadas e permitir sincronizar a partir delas.

#### Scenario: Verificar uma fonte desatualizada
- **WHEN** o usuário clica em verificar e a origem mudou
- **THEN** a aba mostra o estado desatualizado e a lista de mudanças

### Requirement: Revisão de valores das colunas na página
Para cada coluna com valores conhecidos, a aba SHALL permitir editar a descrição de cada valor e SHALL destacar os valores sem descrição e os obsoletos.

#### Scenario: Descrever um valor novo
- **WHEN** o usuário descreve um valor marcado como sem descrição
- **THEN** o destaque some e a descrição aparece na prévia do contexto

### Requirement: Andamento das consultas na página
Enquanto a Maria consulta dados, a página SHALL exibir na mensagem do assistente a descrição de cada evento `activity` recebido, mantendo o indicador de resposta em andamento até o primeiro fragmento de texto ou bloco.

#### Scenario: Consulta em andamento
- **WHEN** a página recebe `activity` com "Buscando projetos sobre dengue"
- **THEN** a mensagem do assistente mostra essa descrição até a resposta começar a aparecer

### Requirement: Gráficos e tabelas nas respostas
A página SHALL renderizar os blocos `chart` e `table` das respostas, tanto no streaming quanto ao reabrir a conversa, da mesma forma que na aba de contrato, e SHALL funcionar a 375px de largura sem rolagem horizontal da página.

#### Scenario: Resposta com gráfico
- **WHEN** a resposta da Maria tem um texto e um gráfico
- **THEN** a página mostra o texto renderizado seguido do gráfico

#### Scenario: Conversa reaberta
- **WHEN** o usuário reabre uma conversa com uma tabela numa resposta anterior
- **THEN** a tabela aparece renderizada no histórico

### Requirement: Colunas pesquisáveis na página
A aba do catálogo SHALL permitir alternar o interruptor **pesquisável** de cada coluna da entidade selecionada.

#### Scenario: Alternar pesquisável
- **WHEN** o usuário liga **pesquisável** na coluna `resumo`
- **THEN** a prévia do contexto passa a indicar que a coluna aceita busca textual

### Requirement: Banner de limite de perguntas
Quando a API recusar uma mensagem com HTTP 429 porque a conversa atingiu o limite de perguntas, a página SHALL remover a pergunta não enviada e exibir um banner com a mensagem da API e a orientação de criar uma nova conversa.

#### Scenario: Conversa no limite de perguntas
- **WHEN** o usuário envia uma pergunta numa conversa que atingiu o limite de perguntas
- **THEN** a página exibe o banner com a mensagem de limite de perguntas e a orientação para usar "+ Nova conversa", e a pergunta não fica na conversa
