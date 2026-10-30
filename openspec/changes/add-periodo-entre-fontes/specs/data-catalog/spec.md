# Spec Delta

## MODIFIED Requirements

### Requirement: Consultas entre fontes no contexto
Com ao menos uma ligação ativa entre fontes incluídas, o contexto SHALL ter a seção "Consultas entre fontes", com as ligações, o formato `fonte.schema.tabela`, a orientação de informar a cobertura devolvida e o alcance do limite de linhas. Sem ligação ativa, a seção MUST ficar de fora.

#### Scenario: Ligação ativa
- **WHEN** fomento e Simcc estão ativos e a ligação pelo Lattes está ligada
- **THEN** a seção lista a ligação e a prévia de conceitos a mostra

#### Scenario: Ligação desligada
- **WHEN** a ligação está desligada
- **THEN** a seção não aparece

## ADDED Requirements

### Requirement: Alcance do limite de linhas no contexto
A seção "Consultas entre fontes" SHALL dizer que o limite vale para as linhas devolvidas e não para as linhas cruzadas, que perguntas sobre todo um grupo se respondem com agregação e que períodos podem ser comparados entre fontes, em consulta sem CTE para manter a cobertura.

#### Scenario: Orientação presente
- **WHEN** a seção é gerada com uma ligação ativa
- **THEN** o texto diz que o limite de linhas não restringe o cruzamento e orienta usar agregação

### Requirement: Política de produção durante a bolsa
A política de `pesquisadores` no seed SHALL orientar: comparar o ano da produção com os anos de início e término da bolsa, considerar sem limite final a bolsa sem término e contar produções sem repetir coautores, por DOI ou por título e ano.

#### Scenario: Receita na política
- **WHEN** a seção de conceitos é gerada a partir do seed
- **THEN** a política de `pesquisadores` traz a comparação por ano, a bolsa sem término e a contagem sem coautores repetidos

### Requirement: Filtro de vigência só quando pedido
A política de `pesquisadores` no seed SHALL mandar aplicar o filtro de vigência só quando a pergunta pedir esse período. Sem esse pedido, MUST considerar toda a produção dos bolsistas.

#### Scenario: Pergunta sem período
- **WHEN** a seção de conceitos é gerada a partir do seed
- **THEN** a política de `pesquisadores` manda não filtrar pela vigência quando a pergunta não pedir o período

### Requirement: Ressalvas da produção durante a bolsa
A política de `pesquisadores` no seed SHALL mandar dizer na resposta que a comparação é por ano e que a vigência da bolsa não prova que ela financiou a produção.

#### Scenario: Ressalvas na política
- **WHEN** a seção de conceitos é gerada a partir do seed
- **THEN** a política de `pesquisadores` manda declarar a comparação por ano e a ressalva sobre financiamento
