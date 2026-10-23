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

### Requirement: Impressão digital do schema
Cada sincronização bem-sucedida SHALL registrar na fonte uma impressão digital da estrutura lida: entidades e tipos, colunas com tipo, nulabilidade e chave primária, chaves estrangeiras e valores de enum. A ordem de leitura MUST NOT alterar a impressão digital.

#### Scenario: Sincronização registra a impressão digital
- **WHEN** uma fonte é sincronizada
- **THEN** a fonte fica com estado `up_to_date` e sem defasagem registrada

### Requirement: Verificação de defasagem
O sistema SHALL verificar uma fonte sob demanda, lendo o schema atual da origem em modo somente leitura e comparando-o com a impressão digital da última sincronização, sem alterar o catálogo editorial. O estado da fonte SHALL ser um entre `unknown` (nunca verificada nem sincronizada), `up_to_date`, `outdated` e `error`. A fonte SHALL guardar a data da última verificação.

#### Scenario: Schema inalterado
- **WHEN** a origem não mudou desde a sincronização e a fonte é verificada
- **THEN** o estado é `up_to_date` e não há diff

#### Scenario: Schema alterado
- **WHEN** uma coluna foi adicionada na origem e a fonte é verificada
- **THEN** o estado é `outdated` e o catálogo continua sem a coluna

#### Scenario: Origem inacessível na verificação
- **WHEN** a verificação não consegue ler a origem
- **THEN** o estado é `error`, a mensagem fica registrada na fonte sem a URL de conexão e o catálogo não muda

### Requirement: Diff da defasagem
Uma fonte `outdated` SHALL expor o que mudou em relação ao catálogo: entidades e colunas novas e ausentes, colunas com tipo, nulabilidade ou chave primária alterados, valores de enum novos e removidos e a quantidade de relacionamentos novos e ausentes. O diff SHALL corresponder ao que a sincronização seguinte aplicaria.

#### Scenario: Diff de coluna removida e enum novo
- **WHEN** uma coluna catalogada foi removida e um enum ganhou um valor
- **THEN** o diff lista a coluna como ausente e o valor como novo

### Requirement: Verificação periódica
O sistema SHALL verificar todas as fontes ativas ao iniciar e depois no intervalo definido por `CATALOG_CHECK_INTERVAL_SECONDS` (padrão 3600). O valor `0` SHALL desligar a verificação periódica. Fontes desativadas MUST NOT ser verificadas. A falha numa fonte MUST NOT impedir a verificação das demais nem os ciclos seguintes.

#### Scenario: Uma fonte falha
- **WHEN** um ciclo verifica duas fontes e a primeira está inacessível
- **THEN** a primeira fica em `error` e a segunda é verificada normalmente

#### Scenario: Fonte desativada
- **WHEN** um ciclo roda com uma fonte desativada
- **THEN** a fonte desativada não é verificada

### Requirement: Sincronização automática
Cada fonte SHALL ter o interruptor `auto_sync`, desligado por padrão e configurável pela API e pelo YAML. Quando ligado, uma verificação que detecte defasagem SHALL sincronizar a fonte imediatamente, com as mesmas regras da sincronização manual, e a resposta SHALL incluir o resumo da sincronização.

#### Scenario: Defasagem com sincronização automática
- **WHEN** uma fonte com `auto_sync` ligado é verificada após uma tabela nova surgir na origem
- **THEN** a tabela entra no catálogo oculta e o estado é `up_to_date`

#### Scenario: Defasagem sem sincronização automática
- **WHEN** a mesma situação ocorre com `auto_sync` desligado
- **THEN** o estado é `outdated` e a tabela não entra no catálogo

### Requirement: Valores de enum
A sincronização SHALL ler os valores dos tipos enum nativos da origem para cada coluna. A API SHALL expor, por coluna, os valores atuais da origem, os valores sem descrição editorial e os valores descritos que não existem mais na origem (obsoletos). A sincronização SHALL relatar os valores novos em colunas cujo enum já era conhecido.

#### Scenario: Valor novo no enum
- **WHEN** o enum de `status` ganha o valor `SUSPENSA` e a fonte é sincronizada
- **THEN** o relatório lista o valor novo e a coluna o expõe como sem descrição

### Requirement: Valores de enum no contexto do modelo
Para colunas com enum conhecido, a prévia do contexto SHALL listar todos os valores atuais da origem, com a descrição editorial quando houver. Valores obsoletos MUST NOT aparecer no contexto.

#### Scenario: Valor sem descrição no contexto
- **WHEN** o enum tem um valor sem descrição
- **THEN** o valor aparece na prévia sem descrição, junto dos valores descritos

#### Scenario: Valor obsoleto fora do contexto
- **WHEN** um valor descrito deixou de existir no enum
- **THEN** ele não aparece na prévia

### Requirement: Colunas pesquisáveis
Cada coluna SHALL ter o interruptor editorial **pesquisável** (`searchable`), desligado por padrão, editável pela API e aceito no seed e na exportação YAML. Colunas novas detectadas na sincronização MUST entrar não pesquisáveis, e a sincronização MUST preservar o valor editado.

#### Scenario: Marcar resumo como pesquisável
- **WHEN** o cliente define `searchable` como verdadeiro na coluna `resumo` de `projetos`
- **THEN** o sistema responde 200 e a coluna passa a aceitar busca textual

#### Scenario: Valor inválido
- **WHEN** o cliente define `searchable` como `null`
- **THEN** o sistema responde 422

#### Scenario: Ida e volta pelo YAML
- **WHEN** uma coluna pesquisável é exportada e a fonte é recriada pelo seed com reinicialização
- **THEN** a coluna continua pesquisável

### Requirement: Colunas pesquisáveis no contexto do modelo
A prévia do contexto SHALL indicar, em cada coluna visível e pesquisável, que ela aceita busca textual. Colunas ocultas MUST NOT aparecer mesmo quando pesquisáveis.

#### Scenario: Indicação na prévia
- **WHEN** a coluna `resumo` de `projetos` é visível e pesquisável
- **THEN** a linha da coluna na prévia indica que ela aceita busca textual

### Requirement: Seed do fomento com colunas pesquisáveis
O seed do fomento SHALL marcar como pesquisáveis o título e o resumo dos projetos e os termos de palavras-chave e de áreas do conhecimento.

#### Scenario: Seed em banco vazio
- **WHEN** o seed do fomento é executado num catálogo vazio e a fonte é sincronizada
- **THEN** `projetos.nome`, `projetos.resumo`, `palavras_chave.termo` e `areas_conhecimento.termo` são pesquisáveis
