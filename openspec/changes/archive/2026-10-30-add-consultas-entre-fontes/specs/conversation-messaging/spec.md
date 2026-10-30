## ADDED Requirements

### Requirement: Ferramenta entre fontes no agente
Com ao menos uma ligação ativa entre fontes consultáveis, o modelo SHALL receber a ferramenta `query_across_sources`. Ela MUST contar para `QUERY_MAX_PER_CALL` e para o orçamento de chamadas, como `query_data`, e seu resultado SHALL poder alimentar gráficos e tabelas. Sem ligação ativa, a ferramenta MUST ficar de fora.

#### Scenario: Ferramenta disponível
- **WHEN** fomento e Simcc estão consultáveis e a ligação pelo Lattes está ligada
- **THEN** o modelo recebe `query_across_sources` junto de `query_data`

#### Scenario: Só uma fonte
- **WHEN** só a fonte `fomento` está consultável
- **THEN** o modelo não recebe `query_across_sources`

#### Scenario: Gráfico de resultado entre fontes
- **WHEN** o modelo pede um gráfico com o `result_id` de uma consulta entre fontes
- **THEN** o bloco de gráfico é montado como nos resultados de `query_data`

### Requirement: Cobertura na resposta
O prompt de regras SHALL obrigar o modelo a informar a cobertura de uma consulta entre fontes, dizendo quantas chaves foram encontradas e de quantas, e a não apresentar o total como completo quando a cobertura for parcial.

#### Scenario: Resposta com cobertura parcial
- **WHEN** a consulta devolve cobertura de 1 em 19
- **THEN** a regra orienta o modelo a dizer que só 1 dos 19 bolsistas foi encontrado no Simcc

## MODIFIED Requirements

### Requirement: Evento de atividade
Antes de cada consulta, o streaming SHALL enviar um evento `activity` com `kind` igual a `query`, o nome da fonte (ou das duas fontes, numa consulta entre fontes) e uma descrição curta, em português, do que está sendo consultado. O evento MUST NOT conter SQL, nomes de modelo, níveis ou URLs.

#### Scenario: Consulta anunciada
- **WHEN** o modelo consulta projetos sobre dengue no fomento
- **THEN** o cliente recebe `activity` com `kind` `query`, a fonte "Fomento à pesquisa" e uma descrição como "Buscando projetos sobre dengue"

#### Scenario: Consulta entre fontes anunciada
- **WHEN** o modelo faz uma consulta entre o fomento e o Simcc
- **THEN** o cliente recebe `activity` com os nomes das duas fontes
