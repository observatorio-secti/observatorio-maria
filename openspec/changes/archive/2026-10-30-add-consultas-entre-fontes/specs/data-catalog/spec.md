## ADDED Requirements

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

## MODIFIED Requirements

### Requirement: Ligação com o fomento nas instruções do Simcc
As instruções da fonte `simcc` SHALL dizer que `researcher.lattes_id` equivale a `pesquisadores.lattes` do fomento e que perguntas que relacionam as duas fontes usam a consulta entre fontes. MUST NOT citar limite de Lattes por consulta.

#### Scenario: Regra no contexto do Simcc
- **WHEN** a prévia do contexto da fonte `simcc` é gerada
- **THEN** ela contém a equivalência entre `lattes_id` e `pesquisadores.lattes` e não cita o limite de 100 Lattes
