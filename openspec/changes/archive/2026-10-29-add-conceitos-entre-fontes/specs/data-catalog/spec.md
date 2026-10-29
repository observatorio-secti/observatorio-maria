## ADDED Requirements

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

## MODIFIED Requirements

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
