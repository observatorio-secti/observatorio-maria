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
O sistema SHALL mostrar, por fonte, o texto que o modelo receberá sobre ela. A prévia SHALL incluir as instruções da fonte, as entidades visíveis e presentes (indicando as não consultáveis) e suas colunas visíveis e presentes, com tipo, descrição, valores listados, indicação de acesso `aggregate` e relacionamentos. A prévia MUST NOT incluir itens ocultos ou ausentes. Uma fonte desativada SHALL resultar em contexto vazio.

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
Para colunas com enum conhecido e `list_values` diferente de `never`, a prévia do contexto SHALL listar todos os valores atuais da origem, com a descrição editorial quando houver. Valores obsoletos MUST NOT aparecer no contexto.

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

### Requirement: Exemplos de consulta validados no catálogo
O sistema SHALL permitir associar a cada fonte de dados uma lista de exemplos canônicos de consulta (pares contendo `question` e `sql`), cadastráveis e editáveis via API nos endpoints da fonte. O modelo de dados SHALL guardar os exemplos no banco da própria Maria.

#### Scenario: Cadastrar exemplos na criação da fonte
- **WHEN** o cliente cria uma fonte incluindo lista de exemplos com pergunta e SQL
- **THEN** a fonte é criada e retorna os exemplos cadastrados

#### Scenario: Atualizar exemplos da fonte
- **WHEN** o cliente atualiza os exemplos de uma fonte via `PATCH /catalog/datasources/{id}`
- **THEN** os novos exemplos substituem os anteriores e ficam persistidos

### Requirement: Exemplos no seed e exportação YAML
O sistema SHALL ler a seção `examples:` sob `datasource:` nos arquivos de seed YAML e persistir os pares `question` e `sql`. A exportação (`GET /catalog/datasources/{id}/export`) SHALL incluir os exemplos cadastrados no documento YAML gerado.

#### Scenario: Seed com exemplos
- **WHEN** o comando de seed é executado com um arquivo YAML contendo `examples:`
- **THEN** os exemplos são carregados no catálogo da fonte

#### Scenario: Ida e volta pelo YAML
- **WHEN** uma fonte com exemplos cadastrados é exportada em YAML
- **THEN** o YAML resultante contém a seção `examples` correspondente

### Requirement: Exemplos na prévia do contexto do modelo
A prévia do contexto de uma fonte (`GET /catalog/datasources/{id}/context` e `render_context`) SHALL incluir a seção `## Exemplos de consultas (few-shot)` listando as perguntas e os blocos de código SQL correspondentes quando a fonte contiver exemplos cadastrados. Fontes sem exemplos cadastrados MUST NOT exibir a seção.

#### Scenario: Fonte com exemplos renderiza seção few-shot
- **WHEN** uma fonte ativa possui exemplos cadastrados
- **THEN** o contexto gerado contém a seção `## Exemplos de consultas (few-shot)` com as perguntas e blocos SQL formatados

#### Scenario: Fonte sem exemplos omite a seção
- **WHEN** a fonte ativa não possui exemplos
- **THEN** a seção de exemplos não aparece no contexto gerado

### Requirement: Leitura de valores observados
A sincronização e a verificação periódica SHALL ler os valores distintos das colunas de texto sem enum que estejam visíveis e presentes, em entidades consultáveis e com acesso `full`. A leitura MUST ser somente leitura, com limite de tempo, e MUST NOT tocar colunas ocultas, colunas `aggregate` ou entidades não consultáveis.

#### Scenario: Coluna categórica lida
- **WHEN** `mv_bolsas_metricas.modalidade` está visível, com acesso `full`, e a fonte é sincronizada
- **THEN** a coluna passa a expor os quatro valores existentes na origem, entre eles `Doutorado - Cotas`

#### Scenario: Coluna oculta não é lida
- **WHEN** uma coluna de texto está oculta
- **THEN** nenhum valor dela é lido da origem e seus valores observados ficam nulos

#### Scenario: Coluna somente para agregação não é lida
- **WHEN** uma coluna de texto visível tem acesso `aggregate`
- **THEN** nenhum valor dela é lido da origem

### Requirement: Limite de valores observados
Uma coluna SHALL ter valores observados apenas quando o número de valores distintos não nulos for no máximo `CATALOG_OBSERVED_VALUES_MAX` (padrão 50, mínimo 1). Acima disso, os valores observados MUST ficar nulos, e a coluna é tratada como texto livre. Valores nulos MUST NOT entrar na lista.

#### Scenario: Coluna de texto livre
- **WHEN** a coluna `pesquisadores.nome` tem milhares de valores distintos
- **THEN** seus valores observados ficam nulos

#### Scenario: Limite configurado
- **WHEN** `CATALOG_OBSERVED_VALUES_MAX` é 3 e a coluna tem 4 valores distintos
- **THEN** seus valores observados ficam nulos

### Requirement: Valores observados como dado técnico
Os valores observados SHALL ser guardados em campo técnico próprio, separado dos valores editoriais, e expostos pela API por coluna. Se a leitura de uma coluna falhar ou exceder o tempo, os valores anteriores SHALL ser mantidos e as demais colunas lidas. Os valores observados MUST NOT entrar na impressão digital do schema.

#### Scenario: Dados mudam sem defasagem
- **WHEN** a origem ganha um valor novo de `modalidade` sem mudar a estrutura
- **THEN** a verificação mantém a fonte `up_to_date` e atualiza os valores observados

#### Scenario: Falha numa coluna
- **WHEN** a leitura de uma coluna excede o tempo limite
- **THEN** os valores observados dela permanecem os da leitura anterior e as outras colunas são atualizadas

### Requirement: Pendentes e obsoletos com valores observados
Para colunas com valores observados e sem enum, a API SHALL tratar os valores observados como os valores atuais da origem: os sem descrição editorial SHALL aparecer como pendentes, e os valores editoriais ausentes da origem SHALL aparecer como obsoletos.

#### Scenario: Valor editorial que não existe na origem
- **WHEN** `bolsas.modalidade` tem o valor editorial `Doutorado` e a origem só tem `Doutorado - Cotas`
- **THEN** a API lista `Doutorado` como obsoleto e `Doutorado - Cotas` como sem descrição

### Requirement: Valores observados no contexto do modelo
Para colunas com valores observados, sem enum e com a listagem permitida, a prévia do contexto SHALL listar todos os valores observados, com a descrição editorial quando houver, sob o rótulo "Valores", e MUST NOT listar valores obsoletos. A orientação de usar os valores exatamente como listados SHALL ficar nas regras do prompt, não em cada coluna.

#### Scenario: Valores reais no contexto
- **WHEN** `mv_bolsas_metricas.modalidade` tem valores observados e a listagem é permitida
- **THEN** a prévia lista `Doutorado - Cotas` e os demais valores da origem, sem `Doutorado`

#### Scenario: Sem valores observados nem enum
- **WHEN** a coluna não tem enum nem valores observados
- **THEN** a prévia lista os valores editoriais, como antes

### Requirement: Exemplos conferidos com o catálogo
Cada exemplo few-shot SHALL ser conferido com as mesmas regras de entidades, colunas e funções permitidas que valem para `query_data`. Exemplos que não passam MUST NOT entrar no contexto do modelo. A prévia do contexto SHALL listar os exemplos recusados, cada um com o motivo.

#### Scenario: Exemplo com coluna inexistente
- **WHEN** um exemplo usa `ano` em `mv_bolsas_metricas`, que só tem `ano_inicio`
- **THEN** o exemplo não aparece na seção few-shot e a prévia o lista como recusado, citando a coluna

#### Scenario: Exemplo válido
- **WHEN** todos os exemplos usam entidades e colunas visíveis e presentes
- **THEN** todos aparecem na seção few-shot e nenhum é listado como recusado

### Requirement: Seed do fomento sem valores supostos
O seed do fomento MUST NOT declarar valores para `bolsas.modalidade`, que passam a vir da origem. O exemplo de totais por ano SHALL usar `ano_inicio` em `mv_bolsas_metricas`.

#### Scenario: Seed em banco vazio
- **WHEN** o seed do fomento roda num banco vazio e a fonte é sincronizada
- **THEN** a prévia não contém exemplos recusados e `bolsas.modalidade` lista só os valores da origem

### Requirement: Seed do Simcc
O projeto SHALL fornecer `catalog/simcc.yaml`, que cria a fonte `simcc` com a variável `SIMCC_DATABASE_URL` e o schema `public`. O seed SHALL expor `researcher` e as tabelas de apoio `institution`, `researcher_institution`, `city`, `state` e `researcher_production`, sem a coluna `researcher.institution_id`. Também SHALL expor as tabelas base e as views `mv_canonical_*` de produções e projetos.

#### Scenario: Seed e sincronização
- **WHEN** o seed do Simcc roda num catálogo vazio e a fonte é sincronizada com o banco de leitura do Simcc
- **THEN** `researcher`, `researcher_institution`, `bibliographic_production`, `patent`, `software`, `participation_events`, `research_project` e as sete views `mv_canonical_*` ficam visíveis, consultáveis e presentes

#### Scenario: Colunas do seed existem na origem
- **WHEN** a fonte `simcc` é sincronizada com o banco de leitura do Simcc
- **THEN** nenhuma coluna listada em `catalog/simcc.yaml` fica ausente

#### Scenario: Vínculo antigo fora do contexto
- **WHEN** a prévia do contexto da fonte `simcc` é gerada a partir do seed
- **THEN** `researcher.institution_id` não aparece, e `researcher_institution` aparece com seus relacionamentos para `researcher` e `institution`

### Requirement: Colunas técnicas do Simcc ocultas
O seed do Simcc MUST NOT tornar visíveis colunas de array, JSON ou `tsvector`, nem campos internos do ETL do Simcc, como `sequence_code`, `is_new`, `stars`, `has_image` e `relevance`. Essas colunas SHALL ficar ocultas após a sincronização e fora do contexto do modelo.

#### Scenario: Colunas das views canônicas
- **WHEN** a fonte `simcc` é sincronizada
- **THEN** `search_vector`, `researcher_ids`, `production_ids` e `platform_authors` de `mv_canonical_articles` ficam ocultas e não aparecem na prévia do contexto

### Requirement: Dados pessoais de pesquisadores no Simcc
O seed do Simcc SHALL deixar visíveis, com acesso `full`, o nome, o ORCID e o resumo do currículo de `researcher`, por decisão do usuário. Respostas da Maria SHALL poder citar o nome dos pesquisadores.

#### Scenario: Listagem com nomes
- **WHEN** o modelo consulta `SELECT name, lattes_id FROM public.researcher` na fonte `simcc`
- **THEN** a consulta é aceita pelo validador

### Requirement: Busca textual no Simcc
O seed do Simcc SHALL marcar como pesquisáveis estas colunas: os títulos das produções, patentes, softwares, eventos e projetos; o nome do evento; a descrição dos projetos; o nome e o resumo do pesquisador; e o título, o resumo e as palavras-chave de `mv_canonical_articles`.

#### Scenario: Busca em títulos de artigos
- **WHEN** o modelo usa `MATCH_TEXT(title, 'dengue')` em `mv_canonical_articles`
- **THEN** a consulta é aceita pelo validador

#### Scenario: Coluna não pesquisável
- **WHEN** o modelo usa `MATCH_TEXT` em `bibliographic_production.doi`
- **THEN** a consulta é recusada porque a coluna não aceita busca textual

### Requirement: Instruções do Simcc
As instruções da fonte `simcc` SHALL dizer que as tabelas base têm uma linha por pesquisador autor e servem para perguntas por pesquisador. Para totais de produções, SHALL indicar as views `mv_canonical_*`, que podem estar defasadas. SHALL dizer também que o ano das produções bibliográficas está em `year_`.

#### Scenario: Orientação no contexto
- **WHEN** a prévia do contexto da fonte `simcc` é gerada
- **THEN** ela contém a orientação de usar as views canônicas para totais e `year_` para o ano

### Requirement: Exemplos do Simcc conferidos com o catálogo
O seed do Simcc SHALL trazer exemplos few-shot, e todos MUST passar nas regras de entidades, colunas e funções permitidas do catálogo semeado.

#### Scenario: Nenhum exemplo recusado
- **WHEN** o seed do Simcc roda num catálogo vazio e as colunas do arquivo estão presentes
- **THEN** todos os exemplos são aceitos e nenhum aparece como recusado na prévia

### Requirement: Seed do Simcc sem valores supostos
O seed do Simcc MUST NOT declarar valores para colunas categóricas de texto, como `type`, `qualis`, `nature`, `category`, `status` e `form_participation`. Os valores dessas colunas SHALL vir da origem como valores observados.

#### Scenario: Colunas sem valores declarados
- **WHEN** `catalog/simcc.yaml` é carregado
- **THEN** nenhuma coluna do arquivo declara `values`

### Requirement: Ligação com o fomento nas instruções do Simcc
As instruções da fonte `simcc` SHALL dizer que `researcher.lattes_id` equivale a `pesquisadores.lattes` do fomento e que perguntas que relacionam as duas fontes usam a consulta entre fontes. MUST NOT citar limite de Lattes por consulta.

#### Scenario: Regra no contexto do Simcc
- **WHEN** a prévia do contexto da fonte `simcc` é gerada
- **THEN** ela contém a equivalência entre `lattes_id` e `pesquisadores.lattes` e não cita o limite de 100 Lattes

### Requirement: Fomento aponta para o Simcc
As instruções da fonte `fomento` SHALL dizer que artigos, livros, capítulos, patentes, softwares, eventos e projetos do currículo dos pesquisadores estão na fonte `simcc`, ligada pelo Lattes.

#### Scenario: Regra no contexto do fomento
- **WHEN** a prévia do contexto da fonte `fomento` é gerada a partir do seed
- **THEN** ela indica a fonte `simcc` para produções dos pesquisadores

### Requirement: Conceitos do catálogo
O catálogo SHALL guardar conceitos: assuntos que podem aparecer em mais de uma fonte, como projetos, instituições e pesquisadores. Um conceito tem identificador (slug minúsculo, imutável), rótulo, descrição, sinônimos e política de resposta. Conceitos são dado editorial e MUST NOT ser criados, alterados ou removidos pela sincronização de schema.

#### Scenario: Sincronização não toca conceitos
- **WHEN** uma fonte é sincronizada depois de um conceito ser editado
- **THEN** o conceito e o vínculo das entidades com ele continuam como estavam

### Requirement: Gestão de conceitos
O sistema SHALL permitir criar, listar, detalhar, editar e excluir conceitos pela API em `/catalog/concepts`. A listagem SHALL trazer, para cada conceito, as entidades vinculadas com a fonte de cada uma. Um identificador repetido MUST ser recusado com 409.

#### Scenario: Criar conceito
- **WHEN** o cliente cria o conceito `projetos` com rótulo e política
- **THEN** o sistema responde 201 e o conceito aparece na listagem

#### Scenario: Identificador repetido
- **WHEN** o cliente cria um conceito com um identificador que já existe
- **THEN** o sistema responde 409 e nada muda

### Requirement: Conceito da entidade
O `PATCH` de entidade SHALL aceitar o identificador de um conceito ou nulo, e o detalhe da entidade SHALL mostrar o conceito. Uma entidade aponta para no máximo um conceito. Um conceito inexistente MUST ser recusado com 422. Excluir um conceito SHALL desvincular as entidades sem excluí-las.

#### Scenario: Vincular entidade
- **WHEN** o cliente vincula `public.projetos` do fomento ao conceito `projetos`
- **THEN** o detalhe da entidade mostra o conceito `projetos`

#### Scenario: Excluir conceito vinculado
- **WHEN** o cliente exclui um conceito com duas entidades vinculadas
- **THEN** as entidades continuam no catálogo, sem conceito

### Requirement: Seed de conceitos
O comando de seed SHALL aceitar um arquivo YAML de conceitos, com as entidades de cada conceito no formato `fonte:schema.entidade`, e aplicá-lo depois dos arquivos de fontes. Entidades inexistentes no catálogo SHALL ser ignoradas com aviso. Um arquivo inválido MUST ser recusado sem alterar o catálogo.

#### Scenario: Seed com as fontes
- **WHEN** `task seed` roda num catálogo vazio com `catalog/concepts.yaml`, `fomento.yaml` e `simcc.yaml`
- **THEN** os três conceitos são criados e vinculados às entidades das duas fontes

#### Scenario: Fonte ausente
- **WHEN** o arquivo de conceitos cita uma entidade de uma fonte que não está no catálogo
- **THEN** o seed cria o conceito, avisa sobre a entidade e segue

### Requirement: Seed de conceitos não destrutivo
O seed de conceitos SHALL criar só os conceitos que não existem e vincular só as entidades que estão sem conceito. MUST NOT sobrescrever conceitos ou vínculos existentes, exceto com a opção de reinicialização, que recria os conceitos do arquivo e seus vínculos.

#### Scenario: Política editada mantida
- **WHEN** a política de um conceito foi editada pela API e o seed roda de novo
- **THEN** a política editada é mantida

### Requirement: Exportação de conceitos
O sistema SHALL exportar os conceitos em YAML no formato aceito pelo seed, de modo que exportar e fazer o seed com reinicialização reproduza os mesmos conceitos e vínculos.

#### Scenario: Ida e volta
- **WHEN** os conceitos são exportados e o arquivo é usado num seed com reinicialização
- **THEN** os conceitos e os vínculos resultantes são iguais aos exportados

### Requirement: Seção de conceitos do contexto
O sistema SHALL gerar a seção "Conceitos em várias fontes" com cada conceito que tenha entidades visíveis e presentes em pelo menos duas fontes ativas. Para cada um, SHALL listar rótulo, descrição, política e as entidades de cada fonte. A API SHALL oferecer a prévia dessa seção.

#### Scenario: Conceito em duas fontes
- **WHEN** `projetos` tem entidades visíveis no fomento e no Simcc, ambos ativos
- **THEN** a prévia lista o conceito com a política e as entidades das duas fontes

#### Scenario: Conceito numa fonte só
- **WHEN** a fonte `simcc` está desativada
- **THEN** a seção não lista conceitos cujas entidades só restaram no fomento

### Requirement: Conceito no contexto da fonte
No contexto de cada fonte, a seção de uma entidade vinculada a um conceito SHALL indicar o rótulo do conceito.

#### Scenario: Entidade com conceito
- **WHEN** a prévia do contexto do fomento é gerada com `public.projetos` vinculada a `projetos`
- **THEN** a seção da entidade indica o conceito "Projetos"

### Requirement: Política inicial dos conceitos
O seed SHALL criar `projetos`, `instituicoes` e `pesquisadores`. Cada política SHALL dizer o que o conceito significa em cada fonte e qual fonte responde pelo sentido da pergunta. Sem sentido definido, SHALL usar uma fonte padrão, dizer de qual fonte é o número e mencionar a outra numa frase. MUST proibir somar as duas fontes.

#### Scenario: Pergunta genérica sobre projetos
- **WHEN** a seção de conceitos é gerada a partir do seed
- **THEN** a política de `projetos` indica o fomento como padrão e manda mencionar os projetos do currículo Lattes no Simcc

### Requirement: Exemplos sem tema repetido entre fontes
Os seeds das fontes MUST NOT trazer exemplos few-shot com a mesma pergunta ou o mesmo tema de busca em fontes diferentes. As regras do prompt da Maria SHALL ilustrar `MATCH_TEXT` com termos genéricos, sem tema de pesquisa.

#### Scenario: Seeds do fomento e do Simcc
- **WHEN** os exemplos de `fomento.yaml` e `simcc.yaml` são comparados
- **THEN** nenhuma pergunta se repete e nenhum termo de `MATCH_TEXT` aparece nas duas fontes

### Requirement: Pesquisador e instituição no Simcc
As instruções da fonte `simcc` SHALL dizer que um pesquisador pode ter várias instituições, ligadas por `researcher_institution`. SHALL orientar `COUNT(DISTINCT ...)` ao contar pesquisadores por instituição e dizer que não há correspondência com as instituições do fomento.

#### Scenario: Orientação no contexto
- **WHEN** a prévia do contexto da fonte `simcc` é gerada a partir do seed
- **THEN** ela orienta a junção por `researcher_institution` com contagem distinta de pesquisadores

### Requirement: Listagem de valores por coluna
Cada coluna SHALL ter o campo editorial `list_values`, com os valores `auto` (padrão), `always` ou `never`, editável pela API e pelo YAML de seed e exportação. Um valor fora desses MUST ser recusado com 422. A sincronização MUST NOT alterar o campo.

#### Scenario: Nunca listar
- **WHEN** o cliente define `list_values` como `never` numa coluna com valores observados
- **THEN** o sistema responde 200 e a prévia do contexto não lista os valores da coluna

#### Scenario: Valor inválido
- **WHEN** o cliente define `list_values` como `sim`
- **THEN** o sistema responde 422

### Requirement: Regra automática de listagem de valores
Com `list_values` em `auto`, uma coluna SHALL listar valores no contexto se tiver enum ou valores com descrição editorial. Com só valores observados, SHALL listá-los apenas se a coluna não for pesquisável, tiver no máximo `CATALOG_CONTEXT_VALUES_MAX` valores (padrão 20) e os valores tiverem até 30 caracteres em média.

#### Scenario: Categoria curta
- **WHEN** `qualis` tem 10 valores observados curtos, não é pesquisável e está em `auto`
- **THEN** a prévia lista os 10 valores

#### Scenario: Muitos valores
- **WHEN** uma coluna em `auto` tem 38 valores observados e o limite é 20
- **THEN** a prévia não lista os valores

#### Scenario: Valores longos ou coluna pesquisável
- **WHEN** uma coluna em `auto` tem 4 títulos observados com 53 caracteres em média, ou é pesquisável
- **THEN** a prévia não lista os valores

#### Scenario: Sempre listar
- **WHEN** a coluna com 38 valores observados está em `always`
- **THEN** a prévia lista os 38 valores

### Requirement: Configuração do limite de valores no contexto
O sistema SHALL ler `CATALOG_CONTEXT_VALUES_MAX` (inteiro, mínimo 1, padrão 20) da configuração. O limite vale só para o que entra no contexto; a leitura e o armazenamento dos valores observados continuam regidos por `CATALOG_OBSERVED_VALUES_MAX`.

#### Scenario: Limite configurado
- **WHEN** `CATALOG_CONTEXT_VALUES_MAX` é 5 e uma coluna em `auto` tem 6 valores observados curtos
- **THEN** a prévia não lista os valores, e os 6 continuam guardados na coluna

### Requirement: Seeds sem listagem de valores não categóricos
Os seeds do fomento e do Simcc SHALL marcar com `list_values: never` as colunas visíveis de texto que não são categorias: identificadores externos (ORCID), nomes (instituições, cidades, estados, editoras, territórios), datas guardadas como texto e indicadores numéricos guardados como texto (JCR).

#### Scenario: ORCID fora da lista de valores
- **WHEN** o seed do Simcc roda e a fonte é sincronizada com poucos pesquisadores
- **THEN** a prévia mostra a coluna `orcid` sem listar valores

### Requirement: Relacionamentos na linha da coluna
Na prévia do contexto, cada relacionamento ligado entre entidades incluídas SHALL aparecer na linha da coluna de origem como `→ schema.entidade.coluna`, e a seção "Relacionamentos" MUST NOT aparecer. Um relacionamento com mais de uma coluna SHALL ser indicado na linha da primeira coluna, com todas as colunas das duas pontas.

#### Scenario: Chave estrangeira
- **WHEN** `bibliographic_production.researcher_id` referencia `researcher.id` e as duas entidades estão incluídas
- **THEN** a linha de `researcher_id` termina com `→ public.researcher.id` e não há seção "Relacionamentos"

#### Scenario: Ponta oculta
- **WHEN** a entidade de destino do relacionamento está oculta
- **THEN** a linha da coluna de origem não indica o relacionamento

### Requirement: Ligações entre fontes
O catálogo SHALL guardar ligações entre fontes: uma coluna de cada fonte, com descrição e interruptor de ligada. Ligações são dado editorial e MUST NOT ser criadas, alteradas ou removidas pela sincronização. As duas colunas MUST ser de fontes diferentes.

#### Scenario: Sincronização preserva a ligação
- **WHEN** uma fonte é sincronizada depois de uma ligação ser desligada
- **THEN** a ligação continua desligada

#### Scenario: Coluna some da origem
- **WHEN** uma coluna da ligação fica ausente
- **THEN** a ligação continua guardada, mas não vale para consultas nem entra no contexto

### Requirement: Gestão de ligações entre fontes
O sistema SHALL permitir criar, listar, editar e excluir ligações pela API em `/catalog/links`. Uma ligação entre colunas inexistentes, da mesma fonte ou repetida MUST ser recusada com 422 ou 409.

#### Scenario: Criar ligação
- **WHEN** o cliente cria a ligação entre `pesquisadores.lattes` e `researcher.lattes_id`
- **THEN** o sistema responde 201 e a ligação aparece na listagem

#### Scenario: Mesma fonte
- **WHEN** o cliente cria uma ligação entre duas colunas do fomento
- **THEN** o sistema responde 422

### Requirement: Seed e exportação de ligações
O arquivo de conceitos SHALL aceitar `links`, com as colunas no formato `fonte:schema.entidade.coluna`, aplicadas com as mesmas regras do seed de conceitos. A exportação de conceitos SHALL incluir as ligações. O seed SHALL criar a ligação pelo Lattes entre `fomento` e `simcc`.

#### Scenario: Seed em catálogo vazio
- **WHEN** `task seed` roda num catálogo vazio
- **THEN** a ligação pelo Lattes é criada

#### Scenario: Ligação editada mantida
- **WHEN** a ligação foi desligada pela API e o seed roda de novo
- **THEN** ela continua desligada

### Requirement: Consultas entre fontes no contexto
Com ao menos uma ligação ativa entre fontes incluídas, o contexto SHALL ter a seção "Consultas entre fontes", com as ligações, o formato `fonte.schema.tabela` e a orientação de informar a cobertura devolvida. Sem ligação ativa, a seção MUST ficar de fora.

#### Scenario: Ligação ativa
- **WHEN** fomento e Simcc estão ativos e a ligação pelo Lattes está ligada
- **THEN** a seção lista a ligação e a prévia de conceitos a mostra

#### Scenario: Ligação desligada
- **WHEN** a ligação está desligada
- **THEN** a seção não aparece
