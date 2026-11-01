# Spec Delta

## MODIFIED Requirements

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

### Requirement: Ligações entre fontes na página
A aba "Entre fontes" do catálogo SHALL listar as ligações entre fontes, com indicação das que têm coluna ausente, e permitir criar, ligar, desligar e excluir ligações. Erros da API SHALL ser exibidos na aba.

#### Scenario: Desligar uma ligação
- **WHEN** o usuário desliga a ligação pelo Lattes
- **THEN** a prévia da seção deixa de mostrar "Consultas entre fontes"

#### Scenario: Ligação inválida
- **WHEN** o usuário cria uma ligação entre duas colunas da mesma fonte
- **THEN** a aba exibe a mensagem de erro da API

## ADDED Requirements

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
