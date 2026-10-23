# data-catalog Specification

## Purpose
Catálogo das fontes de dados externas que a Maria pode usar: o que cada banco contém, o que o modelo enxerga e como interpreta, o que pode ser consultado, e como essa configuração é inicializada (YAML), sincronizada com o schema real e revisada antes de chegar ao modelo.

## Requirements

### Requirement: Catálogo guardado no banco da Maria
O sistema SHALL guardar o catálogo (fontes, entidades, colunas e relacionamentos) no banco da própria Maria. O sistema MUST NOT criar, alterar ou remover objetos nem dados nos bancos de origem.

#### Scenario: Sincronização não altera a origem
- **WHEN** uma fonte é sincronizada
- **THEN** o sistema apenas lê o schema da origem, numa conexão em modo somente leitura

### Requirement: Gestão de fontes de dados
O sistema SHALL permitir criar, listar, detalhar, editar e excluir fontes de dados. Uma fonte tem identificador (slug minúsculo, imutável), nome, descrição, instruções de negócio para a IA, nome da variável de ambiente com a URL de conexão, schemas a ler (padrão `public`) e indicador de ativa.

#### Scenario: Criar fonte
- **WHEN** o cliente cria a fonte `fomento` com a variável `FOMENTO_DATABASE_URL`
- **THEN** o sistema responde 201 com a fonte, sem entidades

#### Scenario: Identificador duplicado
- **WHEN** o cliente cria uma fonte com um identificador já existente
- **THEN** o sistema responde 409

#### Scenario: Identificador inválido
- **WHEN** o cliente cria uma fonte com identificador fora do padrão de slug
- **THEN** o sistema responde 422

#### Scenario: Excluir fonte
- **WHEN** o cliente exclui uma fonte
- **THEN** o sistema responde 204 e remove do catálogo suas entidades, colunas e relacionamentos

#### Scenario: Fonte inexistente
- **WHEN** o cliente acessa uma fonte que não existe
- **THEN** o sistema responde 404

### Requirement: Credenciais fora do catálogo
A URL de conexão MUST NOT ser guardada no catálogo nem devolvida pela API; a fonte guarda apenas o nome da variável de ambiente.

#### Scenario: Fonte devolvida sem URL
- **WHEN** o cliente detalha uma fonte
- **THEN** a resposta contém o nome da variável de ambiente e nenhuma URL de conexão

### Requirement: Resumo das fontes
A listagem de fontes SHALL informar, por fonte, o total de entidades, quantas estão visíveis, quantas são consultáveis e a data da última sincronização.

#### Scenario: Contagens após configurar
- **WHEN** uma fonte tem três entidades, duas visíveis e uma consultável
- **THEN** a listagem mostra 3 entidades, 2 visíveis e 1 consultável

### Requirement: Sincronização de schema
O sistema SHALL sincronizar uma fonte lendo da origem as tabelas, views e views materializadas dos schemas configurados, com suas colunas (tipo, nulabilidade, chave primária e ordem) e chaves estrangeiras. Itens novos SHALL entrar ocultos e não consultáveis. A resposta SHALL resumir o que foi adicionado e o que ficou ausente.

#### Scenario: Primeira sincronização
- **WHEN** uma fonte sem entidades é sincronizada
- **THEN** todas as tabelas e views da origem entram no catálogo como presentes, ocultas e não consultáveis, com suas colunas ocultas e os relacionamentos das chaves estrangeiras

### Requirement: Preservação da configuração na sincronização
A sincronização SHALL atualizar apenas os dados técnicos e MUST preservar a configuração editorial (rótulos, descrições, sinônimos, valores e interruptores). Itens que deixaram de existir na origem SHALL ser marcados como ausentes, sem perder a configuração, e voltar a presentes se reaparecerem.

#### Scenario: Configuração preservada
- **WHEN** uma entidade foi descrita e tornada visível e a fonte é sincronizada de novo
- **THEN** a descrição e os interruptores continuam iguais

#### Scenario: Tabela removida da origem
- **WHEN** uma tabela catalogada deixa de existir na origem e a fonte é sincronizada
- **THEN** a entidade é marcada como ausente e mantém sua configuração

### Requirement: Falhas de sincronização
Uma sincronização que falhe MUST NOT alterar o catálogo.

#### Scenario: Variável de conexão não definida
- **WHEN** a variável de ambiente da fonte não está definida
- **THEN** o sistema responde 422 indicando o nome da variável

#### Scenario: Origem inacessível
- **WHEN** a conexão com a origem falha
- **THEN** o sistema responde 502 e o catálogo não é alterado

### Requirement: Configuração de entidades
O sistema SHALL listar as entidades de uma fonte e detalhar cada uma com suas colunas. O sistema SHALL permitir editar, por entidade, rótulo, descrição, sinônimos e os interruptores **visível** (o modelo enxerga a entidade) e **consultável** (o modelo pode consultá-la). Uma entidade consultável MUST ser visível: ocultar uma entidade a torna não consultável, e tornar consultável uma entidade oculta SHALL ser rejeitado.

#### Scenario: Tornar visível e consultável
- **WHEN** o cliente marca uma entidade como visível e consultável
- **THEN** o sistema responde 200 com os dois interruptores ligados

#### Scenario: Ocultar entidade consultável
- **WHEN** o cliente oculta uma entidade consultável
- **THEN** a entidade fica oculta e não consultável

#### Scenario: Consultável sem ser visível
- **WHEN** o cliente marca como consultável uma entidade que continua oculta
- **THEN** o sistema responde 422

### Requirement: Configuração de colunas
O sistema SHALL permitir editar, por coluna, rótulo, descrição, sinônimos, valores conhecidos (cada um com valor e significado), o interruptor **visível** e o **acesso**: `full` (o modelo pode ler os valores) ou `aggregate` (o modelo só pode filtrar, agrupar e agregar, sem listar valores individuais; usado para dados pessoais).

#### Scenario: Coluna sensível
- **WHEN** o cliente define o acesso de uma coluna como `aggregate`
- **THEN** o sistema responde 200 e a prévia do contexto indica que a coluna é somente para agregação

#### Scenario: Acesso inválido
- **WHEN** o cliente define um acesso diferente de `full` e `aggregate`
- **THEN** o sistema responde 422

### Requirement: Configuração de relacionamentos
O sistema SHALL listar os relacionamentos de uma fonte (entidade e colunas de origem, entidade e colunas de destino) e permitir ligar, desligar e descrever cada um. Relacionamentos vindos de chaves estrangeiras SHALL ser mantidos pela sincronização. Relacionamentos declarados no YAML que não correspondem a chaves estrangeiras SHALL ser preservados como manuais.

#### Scenario: Desligar relacionamento
- **WHEN** o cliente desliga um relacionamento
- **THEN** ele deixa de aparecer na prévia do contexto

### Requirement: Seed via YAML
O sistema SHALL carregar a configuração inicial de uma fonte a partir de um arquivo YAML (fonte, entidades, colunas e relacionamentos) por um comando de linha. Entidades e colunas listadas no arquivo SHALL ser visíveis por padrão, e entidades listadas SHALL ser consultáveis por padrão, salvo indicação em contrário. Um arquivo inválido MUST ser rejeitado sem alterar o catálogo.

#### Scenario: Seed inicial
- **WHEN** o seed de `catalog/fomento.yaml` é executado com o catálogo vazio
- **THEN** a fonte, as entidades, as colunas e os relacionamentos do arquivo são criados

### Requirement: Seed não destrutivo
O seed SHALL criar apenas o que ainda não existe no catálogo e MUST NOT sobrescrever configuração existente, exceto com a opção explícita de reinicialização, que recria a fonte a partir do arquivo.

#### Scenario: Seed não sobrescreve edições
- **WHEN** uma descrição foi editada pela API e o seed é executado de novo
- **THEN** a descrição editada é mantida

#### Scenario: Reinicialização
- **WHEN** o seed é executado com a opção de reinicialização
- **THEN** a fonte é recriada exatamente como no arquivo

#### Scenario: Arquivo inválido
- **WHEN** o YAML tem um acesso de coluna inválido
- **THEN** o comando falha com a mensagem de validação e o catálogo não muda

### Requirement: Exportação para YAML
O sistema SHALL exportar a configuração atual de uma fonte em YAML no mesmo formato aceito pelo seed, de modo que exportar e fazer o seed com reinicialização reproduza a mesma configuração.

#### Scenario: Ida e volta
- **WHEN** a fonte é exportada e o arquivo é usado num seed com reinicialização
- **THEN** a configuração resultante é igual à exportada

### Requirement: Prévia do contexto do modelo
O sistema SHALL mostrar, por fonte, o texto que o modelo receberá sobre ela. A prévia SHALL incluir as instruções da fonte, as entidades visíveis e presentes (indicando as não consultáveis), suas colunas visíveis e presentes (com tipo, descrição, valores conhecidos e indicação de acesso `aggregate`) e os relacionamentos ligados entre entidades incluídas. A prévia MUST NOT incluir itens ocultos ou ausentes. Uma fonte desativada SHALL resultar em contexto vazio.

#### Scenario: Entidade oculta fora do contexto
- **WHEN** uma entidade está oculta
- **THEN** ela e suas colunas não aparecem na prévia

#### Scenario: Fonte desativada
- **WHEN** a fonte está desativada
- **THEN** a prévia é vazia e indica que a fonte está desativada
