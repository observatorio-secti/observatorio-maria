# data-querying Specification Delta

## Requirements

### ADDED Requirement: Envelopamento e sanitização de dados não confiáveis
Todo resultado de consulta retornado à IA SHALL ser envelopado em tags semânticas `<untrusted_database_data>` identificando a fonte. O sistema MUST escapar tags de fechamento presentes nos dados do banco (convertendo em entidades seguras) e MUST truncar textos de células individuais em no máximo 2.000 caracteres indicando truncamento.

#### Scenario: Envelopamento com delimitadores seguros
- **WHEN** a consulta retorna linhas de projetos com resumo textual
- **THEN** a resposta da ferramenta contém os dados encapsulados em `<untrusted_database_data>` e registros estruturados

#### Scenario: Escape de tentativa de quebra de delimitador
- **WHEN** o campo de texto do banco contém `</untrusted_database_data>`
- **THEN** a tag é escapada como `&lt;/untrusted_database_data&gt;` impedindo a fuga do bloco

#### Scenario: Truncamento de célula longa
- **WHEN** uma célula de texto do banco possui 5.000 caracteres
- **THEN** o texto é truncado em 2.000 caracteres com sufixo indicando truncamento

### ADDED Requirement: Mascaramento preventivo de dados pessoais
O sistema SHALL aplicar filtro leve de privacidade sobre valores textuais retornados em consultas antes do envio à IA, substituindo padrões identificáveis de CPF por `[CPF MASCARADO]` e endereços de e-mail por `[E-MAIL MASCARADO]`, sem alterar os dados no banco de origem.

#### Scenario: CPF mascarado no resumo
- **WHEN** o resumo de um projeto contém `pesquisador CPF 123.456.789-00`
- **THEN** o valor entregue à IA substitui o número por `[CPF MASCARADO]`

#### Scenario: E-mail mascarado no texto
- **WHEN** o texto retornado contém `contato: fulano@provedor.com.br`
- **THEN** o valor entregue à IA substitui o endereço por `[E-MAIL MASCARADO]`
