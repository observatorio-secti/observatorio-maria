## ADDED Requirements

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
