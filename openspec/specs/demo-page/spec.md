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

### Requirement: Título do eixo Y nos gráficos
A página SHALL mostrar um título no eixo Y dos gráficos com eixos: o rótulo e a unidade da série, quando há uma só série, ou a unidade, quando todas as séries têm a mesma. Nos demais casos, o eixo Y MUST ficar sem título.

#### Scenario: Uma série
- **WHEN** um gráfico de barras tem uma série com rótulo "Bolsas" e unidade "un"
- **THEN** o eixo Y mostra "Bolsas (un)"

#### Scenario: Séries com a mesma unidade
- **WHEN** um gráfico de linhas tem duas séries com a unidade "R$"
- **THEN** o eixo Y mostra "R$"

#### Scenario: Séries com unidades diferentes
- **WHEN** um gráfico tem duas séries com unidades diferentes
- **THEN** o eixo Y fica sem título

#### Scenario: Gráfico de pizza
- **WHEN** a resposta tem um gráfico de pizza
- **THEN** o gráfico é mostrado sem eixos

### Requirement: Aviso de dados parciais
A página SHALL mostrar, abaixo de um bloco `chart` ou `table` com `truncated` verdadeiro, um aviso com a quantidade de linhas mostradas, tanto no streaming quanto ao reabrir a conversa. Blocos sem o campo ou com valor falso MUST ficar sem aviso.

#### Scenario: Tabela cortada
- **WHEN** a resposta tem uma tabela com 100 linhas e `truncated` verdadeiro
- **THEN** a página mostra, abaixo da tabela, que são exibidas só as primeiras 100 linhas

#### Scenario: Gráfico cortado em conversa reaberta
- **WHEN** o usuário reabre uma conversa com um gráfico cortado
- **THEN** o aviso aparece abaixo do gráfico

#### Scenario: Bloco completo
- **WHEN** o bloco tem `truncated` falso ou não tem o campo
- **THEN** nenhum aviso é mostrado

### Requirement: Rodapé de origem nas respostas
A página SHALL mostrar, abaixo de um bloco `chart` ou `table` com `origin`, as fontes, a descrição e a data da consulta e, quando houver, a cobertura, tanto no streaming quanto ao reabrir a conversa. Blocos sem `origin` MUST ficar sem rodapé.

#### Scenario: Gráfico com origem
- **WHEN** a resposta tem um gráfico com `origin`
- **THEN** a página mostra abaixo dele a fonte, a descrição e a data da consulta no formato pt-BR

#### Scenario: Consulta entre fontes
- **WHEN** a resposta tem uma tabela com duas fontes e cobertura de 1 em 19
- **THEN** o rodapé mostra as duas fontes e que 1 de 19 foi encontrado

#### Scenario: Conversa reaberta
- **WHEN** o usuário reabre uma conversa com um bloco com `origin`
- **THEN** o rodapé aparece abaixo do bloco

#### Scenario: Bloco antigo
- **WHEN** o bloco não tem `origin`
- **THEN** nenhum rodapé é mostrado

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

### Requirement: Conceitos na página
A aba "Catálogo de dados" SHALL listar os conceitos com suas entidades e permitir criar, editar (rótulo, descrição, sinônimos e política) e excluir conceitos. SHALL exibir a prévia da seção de conceitos que o modelo recebe. Erros da API SHALL ser exibidos na aba.

#### Scenario: Editar a política
- **WHEN** o usuário altera a política de um conceito e salva
- **THEN** a prévia da seção de conceitos passa a mostrar a política nova

#### Scenario: Identificador repetido
- **WHEN** o usuário cria um conceito com um identificador que já existe
- **THEN** a aba exibe a mensagem de erro da API e mantém a lista como estava

### Requirement: Conceito da entidade na página
Na edição de uma entidade, a aba SHALL permitir escolher o conceito da entidade, ou nenhum, entre os conceitos existentes.

#### Scenario: Vincular entidade
- **WHEN** o usuário escolhe o conceito "Projetos" para `public.projetos` e salva
- **THEN** a entidade aparece na lista do conceito e a prévia do contexto da fonte indica o conceito

### Requirement: Listagem de valores na página
Na tabela de colunas da entidade, a aba "Catálogo de dados" SHALL permitir escolher, por coluna, se os valores entram no contexto: automático, sempre ou nunca.

#### Scenario: Deixar de listar
- **WHEN** o usuário escolhe "nunca" para uma coluna com valores listados
- **THEN** a prévia do contexto da fonte deixa de listar os valores dessa coluna

### Requirement: Sugestões de perguntas
Com a conversa vazia, a página SHALL mostrar sugestões de perguntas, sorteadas a cada acesso entre uma lista de 10 a 15 perguntas. Clicar numa sugestão SHALL enviá-la como mensagem. As sugestões MUST sair da tela quando a conversa começar.

#### Scenario: Sugestões variam por acesso
- **WHEN** o usuário acessa a página de novo
- **THEN** as sugestões são sorteadas outra vez entre as perguntas da lista

#### Scenario: Enviar uma sugestão
- **WHEN** o usuário clica numa sugestão
- **THEN** a pergunta é enviada como mensagem, a resposta aparece na conversa e as sugestões somem

### Requirement: Ligações entre fontes na página
A subaba "Conceitos" da aba do catálogo SHALL listar as ligações entre fontes, com indicação das que têm coluna ausente, e permitir criar, ligar, desligar e excluir ligações. Erros da API SHALL ser exibidos na aba.

#### Scenario: Desligar uma ligação
- **WHEN** o usuário desliga a ligação pelo Lattes
- **THEN** a prévia da seção deixa de mostrar "Consultas entre fontes"

#### Scenario: Ligação inválida
- **WHEN** o usuário cria uma ligação entre duas colunas da mesma fonte
- **THEN** a aba exibe a mensagem de erro da API

### Requirement: Interromper a geração
Durante a geração, a página SHALL oferecer um botão Parar no lugar de Enviar. Ao parar, a conexão MUST ser encerrada, a pergunta e o texto parcial MUST sair da conversa, a pergunta MUST voltar ao campo de mensagem e a página SHALL informar que nada foi gravado.

#### Scenario: Parar uma resposta em andamento
- **WHEN** o usuário clica em Parar enquanto a Maria gera a resposta
- **THEN** a geração é interrompida, a conversa não ganha mensagens e a pergunta fica no campo de mensagem

#### Scenario: Botão ao fim da resposta
- **WHEN** a resposta termina
- **THEN** o botão volta a ser Enviar

### Requirement: Tentar novamente depois de um erro
Quando o envio falhar por erro temporário, o banner SHALL oferecer "Tentar novamente", que reenvia a mesma pergunta. Erros de limite da conversa (429) e de configuração (503) MUST ficar sem o botão.

#### Scenario: Falha do modelo
- **WHEN** o stream termina com um evento `error`
- **THEN** o banner mostra o erro e o botão, e clicar nele reenvia a pergunta

#### Scenario: Limite de perguntas
- **WHEN** a API recusa a mensagem com HTTP 429
- **THEN** o banner aparece sem "Tentar novamente"

### Requirement: Copiar resposta
Cada resposta da Maria SHALL ter um botão que copia o texto da resposta em Markdown, com confirmação visual. Se a cópia não for possível, a página MUST informar o erro.

#### Scenario: Copiar texto
- **WHEN** o usuário clica em Copiar numa resposta com texto e gráfico
- **THEN** o texto em Markdown vai para a área de transferência e o botão confirma a cópia

#### Scenario: Cópia indisponível
- **WHEN** o navegador não permite usar a área de transferência
- **THEN** a página exibe um aviso de que não foi possível copiar

### Requirement: Baixar gráfico em PNG
Blocos `chart` SHALL oferecer o download de um PNG com fundo opaco, o título e, quando houver, a origem dos dados.

#### Scenario: Gráfico com origem
- **WHEN** o usuário baixa o PNG de um gráfico com `origin`
- **THEN** o arquivo tem o nome derivado do título e mostra título, gráfico e origem

### Requirement: Baixar dados em CSV
Blocos `chart` e `table` SHALL oferecer um CSV com BOM UTF-8, separador `;`, vírgula decimal e cabeçalho com os rótulos. Depois dos dados, após uma linha em branco, o arquivo SHALL trazer o título e, quando houver, o aviso de corte e a origem.

#### Scenario: Tabela com números
- **WHEN** o usuário baixa o CSV de uma tabela com o valor 12.5 na coluna "Orçamento"
- **THEN** o cabeçalho traz "Orçamento" e a célula traz 12,5

#### Scenario: Tabela cortada
- **WHEN** o usuário baixa o CSV de um bloco com `truncated` verdadeiro
- **THEN** as últimas linhas avisam que os dados são parciais

### Requirement: CSV sem fórmulas
Células de texto do CSV que começam com `=`, `+`, `-`, `@`, tabulação ou retorno de carro MUST ser prefixadas com apóstrofo, para não serem executadas como fórmula. Células com `;`, aspas ou quebra de linha MUST ser colocadas entre aspas.

#### Scenario: Texto que parece fórmula
- **WHEN** uma célula de texto contém `=HYPERLINK("http://x")`
- **THEN** o CSV traz o valor com apóstrofo no início, entre aspas e com as aspas internas duplicadas

#### Scenario: Número negativo
- **WHEN** uma célula numérica contém -5
- **THEN** o CSV traz -5, sem apóstrofo

### Requirement: Botões de continuação
A página SHALL mostrar os blocos `suggestions` como botões, apenas na última mensagem da conversa. Clicar num botão SHALL enviar a pergunta como mensagem. Enquanto uma resposta é gerada, os botões MUST ficar ocultos.

#### Scenario: Última resposta
- **WHEN** a conversa tem duas respostas com sugestões
- **THEN** só a última mostra os botões

#### Scenario: Enviar uma continuação
- **WHEN** o usuário clica num botão de continuação
- **THEN** a pergunta é enviada e os botões da resposta anterior somem

#### Scenario: Conversa reaberta
- **WHEN** o usuário reabre uma conversa cuja última resposta tem sugestões
- **THEN** os botões aparecem
