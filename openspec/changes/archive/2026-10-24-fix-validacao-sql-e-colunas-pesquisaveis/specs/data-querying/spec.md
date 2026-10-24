# data-querying Specification Delta

## Requirements

### MODIFIED Requirement: Funções permitidas
A consulta SHALL usar apenas funções de uma lista permitida (agregações, datas, texto, conversões e condicionais comuns, além de `MATCH_TEXT`). Conectores lógicos como `AND`, `OR` e `XOR`, bem como predicados `EXISTS`, SHALL ser permitidos em expressões booleanas e MUST NOT ser tratados como funções proibidas. Qualquer função fora da lista permitida MUST ser recusada.

#### Scenario: Operadores lógicos compostos
- **WHEN** o modelo envia consulta com `WHERE status = 'REGULAR' AND modalidade = 'DCR'`
- **THEN** a consulta é aceita sem erro de função proibida

#### Scenario: Predicado EXISTS em subconsulta
- **WHEN** o modelo envia consulta com `WHERE EXISTS (SELECT 1 FROM public.projetos_palavras_chave WHERE projeto_id = p.id)`
- **THEN** a consulta é aceita sem erro de função proibida

#### Scenario: Função de sistema recusada
- **WHEN** o modelo usa `pg_sleep(10)` ou `sin(id)`
- **THEN** a consulta é recusada antes de chegar à origem

### MODIFIED Requirement: Busca textual
A consulta SHALL aceitar `MATCH_TEXT(coluna, 'termo', ...)`, verdadeira quando a coluna contém ao menos um dos termos, sem diferenciar maiúsculas, minúsculas e acentos. O prompt de regras da Maria MUST orientar o modelo a chamar `MATCH_TEXT` como função com a assinatura `MATCH_TEXT(coluna, 'termo1', 'termo2')`, sem operadores infixos ou operadores de similaridade não padrão. Termos vazios MUST ser recusados.

#### Scenario: Tema com sinônimos
- **WHEN** o modelo filtra projetos por `MATCH_TEXT(resumo, 'dengue', 'aedes aegypti', 'arbovirose')`
- **THEN** voltam os projetos cujo resumo contém qualquer um dos termos
