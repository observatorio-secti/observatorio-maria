# Design

## Context

Motivação em `proposal.md`. `ResultStore` nasce vazio a cada resposta, com ids `r1`, `r2`…. Os blocos gravados têm as linhas exibidas, mas só as colunas pedidas. `show_chart` e `show_table` buscam no `ResultStore`, validam as colunas e copiam `truncated` e `origin`. O histórico passou a trazer valores com `add-valores-no-historico`.

## Goals / Non-Goals

**Goals:**
- Reapresentar dados sem tocar nas origens.
- Procedência fiel: um dado reapresentado mostra quando foi consultado.

**Non-Goals:**
- Cálculos sobre resultados anteriores.

## Decisions

### D1. Reidratar os blocos no `ResultStore`

`result_from_block` converte cada bloco num `QueryResult`, e `ResultStore.restore` o registra com id `hN`. As ferramentas não mudam.

Descartada: uma ferramenta nova de reapresentação. Duplicaria a validação e a montagem dos blocos.

### D2. Ids por ordem cronológica

Um `itertools.count` é compartilhado entre a restauração e os resumos. Os dois percorrem `history` na mesma ordem, então `h1` é o mesmo bloco nos dois lugares.

Descartada: guardar o id no bloco gravado. Mudaria o contrato e deixaria as mensagens antigas sem id.

### D3. Prefixo `h`

Os ids `hN` não colidem com `rN` e indicam ao modelo que o dado é anterior.

Descartada: continuar a numeração `r`. O número de um resultado mudaria conforme a conversa cresce.

### D4. Chaves no resumo

O resumo ganha `Resultado: h1` e `Chaves: ano, total`, porque os rótulos não servem para `show_*`. Com `HISTORY_MAX_ROWS=0`, as chaves continuam presentes.

Descartada: depender dos nomes de campo do XML. Eles somem quando os valores estão desligados.

### D5. Dados gravados são todos os dados reusáveis

Um bloco cortado segue cortado. Uma coluna fora do bloco é recusada, e o modelo pode consultar de novo.

Descartada: guardar o resultado completo. Aumentaria o banco e contrariaria o requisito de não persistir resultados.

### D6. Tipos normalizados na escrita e na leitura

`axis_type` e `table_column_type` convertem os tipos em `show_chart` e `show_table`. Validadores em `ChartAxis` e `TableColumn` aplicam a mesma regra na leitura, para mensagens já gravadas.

Descartada: migrar `messages.content`. O banco de produção não foi inspecionado, e a leitura tolerante cobre qualquer bloco antigo sem reescrever dados.

## Risks / Trade-offs

- [Risco] Dado antigo apresentado como atual → O bloco mantém `origin` com a data da consulta original.
- [Risco] Resumo mais longo em cada pergunta → Acréscimo pequeno, limitado pelo número de blocos da conversa.
- [Risco] Modelo escolher `hN` quando precisava de dado novo → A regra limita o uso a mudanças de apresentação.
