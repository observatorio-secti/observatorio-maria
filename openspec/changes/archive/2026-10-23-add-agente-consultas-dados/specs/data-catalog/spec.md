# Spec Delta

## ADDED Requirements

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
