## MODIFIED Requirements

### Requirement: Mascaramento preventivo de dados pessoais
O sistema SHALL aplicar filtro leve de privacidade sobre valores textuais retornados em consultas, inclusive os aninhados em listas e objetos, antes do envio à IA e da criação de gráficos e tabelas, substituindo padrões identificáveis de CPF por `[CPF MASCARADO]` e endereços de e-mail por `[E-MAIL MASCARADO]`, sem alterar os dados no banco de origem.

#### Scenario: CPF mascarado no resumo
- **WHEN** o resumo de um projeto contém `pesquisador CPF 123.456.789-00`
- **THEN** o valor entregue à IA substitui o número por `[CPF MASCARADO]`

#### Scenario: E-mail mascarado no texto
- **WHEN** o texto retornado contém `contato: fulano@provedor.com.br`
- **THEN** o valor entregue à IA substitui o endereço por `[E-MAIL MASCARADO]`

#### Scenario: Valor aninhado mascarado
- **WHEN** uma coluna da origem traz uma lista ou um objeto com um e-mail
- **THEN** o valor entregue à IA e o bloco mantêm o tipo e trazem `[E-MAIL MASCARADO]`

## ADDED Requirements

### Requirement: Blocos novos sem dados pessoais
Gráficos e tabelas MUST ser mascarados ao serem criados, antes do evento SSE e da gravação. O delta, a mensagem concluída, a leitura pela API, a demo e o CSV SHALL trazer a mesma versão mascarada, inclusive em título e rótulos. Fora a máscara, o texto da célula MUST NOT sofrer escape nem corte.

#### Scenario: Tabela com CPF
- **WHEN** a Maria apresenta uma tabela cuja célula contém `123.456.789-00` e `a@b.com`
- **THEN** o delta SSE, a mensagem gravada e a leitura das mensagens trazem `[CPF MASCARADO]` e `[E-MAIL MASCARADO]`, sem os valores

#### Scenario: Gráfico com CPF no eixo
- **WHEN** a Maria apresenta um gráfico cujo eixo traz um valor com CPF
- **THEN** `data` traz `[CPF MASCARADO]`, e as séries numéricas não mudam

#### Scenario: Texto longo sem corte
- **WHEN** uma célula tem mais de 2.000 caracteres
- **THEN** o bloco traz o texto inteiro, com a máscara aplicada

### Requirement: Mensagens antigas não são reescritas
O sistema MUST NOT reescrever mensagens já gravadas nem mascará-las na leitura. Um gráfico ou tabela novo feito a partir de um bloco antigo SHALL sair mascarado.

#### Scenario: Leitura de mensagem antiga
- **WHEN** uma mensagem gravada antes da mudança contém um CPF num bloco
- **THEN** a leitura das mensagens devolve o bloco como foi gravado

#### Scenario: Reapresentação de bloco antigo
- **WHEN** a Maria reapresenta um bloco antigo com CPF numa nova tabela
- **THEN** a nova tabela traz `[CPF MASCARADO]`
