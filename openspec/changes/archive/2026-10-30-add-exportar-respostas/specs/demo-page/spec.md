# Spec Delta

## ADDED Requirements

### Requirement: Copiar resposta
Cada resposta da Maria SHALL ter um botão que copia o texto da resposta em Markdown, com confirmação visual. Se a cópia não for possível, a página MUST informar o erro.

#### Scenario: Copiar texto
- **WHEN** o usuário clica em Copiar numa resposta com texto e gráfico
- **THEN** o texto em Markdown vai para a área de transferência e o botão confirma a cópia

#### Scenario: Cópia indisponível
- **WHEN** o navegador não permite usar a área de transferência
- **THEN** a página exibe um aviso de que não foi possível copiar

### Requirement: Baixar gráfico em PNG
Blocos `chart` SHALL oferecer o download de um PNG com fundo opaco, o título e, quando houver, a origem dos dados.

#### Scenario: Gráfico com origem
- **WHEN** o usuário baixa o PNG de um gráfico com `origin`
- **THEN** o arquivo tem o nome derivado do título e mostra título, gráfico e origem

### Requirement: Baixar dados em CSV
Blocos `chart` e `table` SHALL oferecer um CSV com BOM UTF-8, separador `;`, vírgula decimal e cabeçalho com os rótulos. Depois dos dados, após uma linha em branco, o arquivo SHALL trazer o título e, quando houver, o aviso de corte e a origem.

#### Scenario: Tabela com números
- **WHEN** o usuário baixa o CSV de uma tabela com o valor 12.5 na coluna "Orçamento"
- **THEN** o cabeçalho traz "Orçamento" e a célula traz 12,5

#### Scenario: Tabela cortada
- **WHEN** o usuário baixa o CSV de um bloco com `truncated` verdadeiro
- **THEN** as últimas linhas avisam que os dados são parciais

### Requirement: CSV sem fórmulas
Células de texto do CSV que começam com `=`, `+`, `-`, `@`, tabulação ou retorno de carro MUST ser prefixadas com apóstrofo, para não serem executadas como fórmula. Células com `;`, aspas ou quebra de linha MUST ser colocadas entre aspas.

#### Scenario: Texto que parece fórmula
- **WHEN** uma célula de texto contém `=HYPERLINK("http://x")`
- **THEN** o CSV traz o valor com apóstrofo no início, entre aspas e com as aspas internas duplicadas

#### Scenario: Número negativo
- **WHEN** uma célula numérica contém -5
- **THEN** o CSV traz -5, sem apóstrofo
