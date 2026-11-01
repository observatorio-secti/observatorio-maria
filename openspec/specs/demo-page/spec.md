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

#### Scenario: Desativar uma fonte
- **WHEN** o usuário desliga "Fonte ativa" na subaba da fonte
- **THEN** o cabeçalho e a aba do banco indicam que a fonte está inativa

### Requirement: Edição de entidades e colunas na página
A aba SHALL listar as entidades com indicação de presença e permitir alternar **visível** e **consultável** e editar rótulo, descrição e sinônimos. Para a entidade selecionada, SHALL permitir alternar a visibilidade, alterar o acesso e editar a descrição de cada coluna.

#### Scenario: Ocultar uma tabela
- **WHEN** o usuário desliga "Usar nas respostas" de uma entidade
- **THEN** a entidade aparece como oculta e some da prévia do contexto

#### Scenario: Coluna somente agregação
- **WHEN** o usuário muda o acesso de uma coluna para `aggregate` nas opções da coluna
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
A aba "Entre fontes" do catálogo SHALL listar as ligações entre fontes, com indicação das que têm coluna ausente, e permitir criar, ligar, desligar e excluir ligações. Erros da API SHALL ser exibidos na aba.

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

### Requirement: Resposta montada por ordem de chegada
Durante o streaming, a página SHALL mostrar textos e blocos na ordem em que chegam, sem redesenhar os gráficos já exibidos. Ao fim, a versão gravada MUST manter a mesma ordem.

#### Scenario: Texto depois de um gráfico
- **WHEN** a resposta tem texto, gráfico e mais texto
- **THEN** a página mostra os três nessa ordem durante a geração e depois de reabrir a conversa

#### Scenario: Exemplo do contrato
- **WHEN** o usuário abre a aba "Contrato de blocos"
- **THEN** o exemplo mostra um texto depois do gráfico

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

### Requirement: Tema claro
A página SHALL usar um único tema claro, com cores sóbrias, mesmo com o sistema em modo escuro. A interface MUST NOT usar emojis nem símbolos decorativos.

#### Scenario: Sistema em modo escuro
- **WHEN** o usuário abre a página com o sistema em modo escuro
- **THEN** a página aparece no tema claro

#### Scenario: Sem emojis
- **WHEN** o usuário navega pelas abas da página
- **THEN** rótulos, botões e avisos não têm emojis

### Requirement: Abas por banco no catálogo
A aba do catálogo SHALL mostrar uma aba para cada fonte cadastrada e uma aba "Entre fontes", no lugar do seletor de fonte. Uma fonte inativa MUST ser indicada na própria aba, por texto além da cor.

#### Scenario: Trocar de banco
- **WHEN** o usuário abre a aba Simcc estando na aba Fomento
- **THEN** a lista de entidades, as subabas e o cabeçalho passam a mostrar o Simcc

#### Scenario: Fonte nova
- **WHEN** uma terceira fonte é cadastrada
- **THEN** ela ganha a própria aba sem mudança na página

### Requirement: Identificação do banco em edição
Em toda subaba de um banco, a página SHALL manter visível um cabeçalho com o nome e o identificador da fonte, o estado do schema e quantas entidades estão em uso. Cada banco MUST ter uma cor própria, repetida na aba e no cabeçalho.

#### Scenario: Banco sempre identificado
- **WHEN** o usuário navega entre as subabas do Simcc
- **THEN** o cabeçalho continua mostrando Simcc, `simcc` e o estado do schema

### Requirement: Conceitos e ligações fora dos bancos
A aba "Entre fontes" SHALL reunir os conceitos, as ligações entre fontes e a prévia da seção de conceitos, que MUST NOT aparecer nas subabas de um banco.

#### Scenario: Abrir Entre fontes
- **WHEN** o usuário abre a aba "Entre fontes"
- **THEN** vê conceitos, ligações e a prévia, sem lista de entidades de um banco

### Requirement: Lista focada nas entidades em uso
A lista de entidades SHALL mostrar por padrão só as visíveis e oferecer "Mostrar ocultas" com a quantidade de ocultas. A busca MUST alcançar também as ocultas. As linhas da lista MUST NOT ter interruptores.

#### Scenario: Lista padrão
- **WHEN** o usuário abre um banco com 24 entidades visíveis de 94
- **THEN** a lista mostra as 24 e "Mostrar ocultas (70)"

#### Scenario: Buscar uma entidade oculta
- **WHEN** o usuário busca o nome de uma entidade oculta com "Mostrar ocultas" desligado
- **THEN** a entidade aparece na lista, identificada como oculta

### Requirement: Essencial da entidade à vista
A edição da entidade SHALL mostrar à vista "Usar nas respostas", rótulo e descrição, e SHALL guardar consultável, sinônimos e conceito em "Opções avançadas". Ligar "Usar nas respostas" MUST deixar a entidade visível e consultável.

#### Scenario: Usar uma entidade oculta
- **WHEN** o usuário liga "Usar nas respostas" numa entidade oculta
- **THEN** a entidade fica visível e consultável

#### Scenario: Só contexto
- **WHEN** o usuário desliga "Consultável" nas opções avançadas
- **THEN** a entidade continua visível e não consultável

### Requirement: Colunas focadas nas visíveis
A tabela de colunas SHALL mostrar por padrão só as colunas visíveis, com nome, tipo, visível e descrição, e oferecer "Mostrar ocultas" com a quantidade. O resumo da entidade MUST continuar indicando o total de colunas.

#### Scenario: Entidade com colunas ocultas
- **WHEN** o usuário abre uma entidade com 8 de 20 colunas visíveis
- **THEN** a tabela mostra as 8 e "Mostrar ocultas (12)"

### Requirement: Opções avançadas da coluna
Cada coluna SHALL oferecer "Opções" com acesso, pesquisável, valores no contexto e a edição dos valores conhecidos. Com as opções fechadas, a coluna MUST mostrar um selo para cada ajuste fora do padrão e para valores a revisar.

#### Scenario: Ajuste fora do padrão
- **WHEN** uma coluna tem acesso `aggregate` e as opções estão fechadas
- **THEN** a linha mostra o selo "só agregação"

#### Scenario: Valores a revisar
- **WHEN** uma coluna tem valores sem descrição
- **THEN** a linha mostra a quantidade a revisar, e "Opções" abre a edição dos valores

### Requirement: Aviso de fonte inativa
Quando a fonte estiver inativa, o cabeçalho do banco SHALL avisar que a Maria não a usa e oferecer um botão que a ativa.

#### Scenario: Ativar pelo aviso
- **WHEN** o usuário clica em "Ativar fonte" no aviso
- **THEN** a fonte fica ativa e o aviso some

### Requirement: Aviso de sincronização automática
Com a sincronização automática desligada, o cabeçalho do banco SHALL informar, de forma discreta, que ela pode ser ligada, e oferecer um botão que a liga.

#### Scenario: Ligar pelo aviso
- **WHEN** o usuário clica em "Ligar" no aviso de sincronização automática
- **THEN** a fonte passa a sincronizar automaticamente e o aviso some

### Requirement: Aviso de entidade indisponível
Na edição, uma entidade oculta SHALL trazer um aviso de que a Maria não a enxerga, e uma entidade visível e não consultável, um aviso de que a Maria a conhece mas não pode consultá-la. Cada aviso SHALL ter um botão que resolve o estado.

#### Scenario: Entidade oculta
- **WHEN** o usuário clica no botão do aviso de uma entidade oculta
- **THEN** a entidade fica visível e consultável e o aviso some

#### Scenario: Entidade não consultável
- **WHEN** o usuário clica em "Permitir consultas" no aviso
- **THEN** a entidade fica consultável e o aviso some

### Requirement: Aviso de consultas entre fontes indisponíveis
Quando nenhuma ligação ativa unir duas fontes ativas, a aba "Entre fontes" SHALL avisar que a Maria não pode cruzar os bancos, dizer o motivo e oferecer a ação correspondente. Com uma ligação valendo, o aviso MUST sumir.

#### Scenario: Fonte inativa
- **WHEN** a única ligação usa uma fonte inativa
- **THEN** o aviso nomeia a fonte e oferece um botão para ativá-la

#### Scenario: Ligação desligada
- **WHEN** todas as ligações estão desligadas
- **THEN** o aviso orienta ligar uma ligação da lista

#### Scenario: Sem ligações
- **WHEN** não há ligações cadastradas
- **THEN** o aviso orienta criar uma ligação

### Requirement: Aviso de ligação sem efeito
Uma ligação ligada que não vale para consultas SHALL indicar que a coluna está oculta ou ausente e oferecer botões que abrem a entidade de cada ponta no respectivo banco.

#### Scenario: Abrir a entidade da ligação
- **WHEN** o usuário clica em abrir a entidade de uma ponta da ligação
- **THEN** a aba muda para o banco dessa ponta com a entidade selecionada
