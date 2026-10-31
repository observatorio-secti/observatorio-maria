# Proposal

## Why

Nas tabelas, colunas de ano aparecem com separador de milhar: a pergunta "Quantos artigos únicos foram publicados por ano desde 2020?" mostrou `2.020`, `2.021`, … `2.026` (issue #6). A inferência de tipos marca o ano como `number`, e a demo formata todo `number` com `toLocaleString`.

## What Changes

- **Coluna de ano como texto:** uma coluna numérica cujo nome indique ano e cujos valores sejam todos inteiros de 1900 a 2100 passa a ter o tipo `string` no bloco `table`. O valor na linha continua inteiro.
- **Blocos gravados:** a mesma regra vale na leitura, então conversas antigas abrem com o ano correto.
- **Streaming:** o bloco enviado em `content.delta` já sai com o tipo corrigido, sem mostrar `2.020` até a mensagem final chegar.
- **Demo:** nenhuma alteração de código. A coluna `string` já é exibida sem formatação; a mudança só é verificada no navegador.

### Fora do escopo

- Novo tipo de coluna `year` no contrato de blocos: exigiria mudança na demo e no `observatorio-front`.
- Gráficos de dispersão com ano no eixo x, cuja escala numérica é formatada pelo Chart.js. Os demais gráficos usam o valor como rótulo e não têm o problema.
- Colunas de ano com outro nome, como `exercicio` ou `safra`.

## Capabilities

### New Capabilities

Nenhuma.

### Modified Capabilities

- `conversation-messaging`: novo requisito para o tipo das colunas de ano no bloco `table`.

## Impact

- **Código:** `src/observatorio_maria/schemas.py` e `src/observatorio_maria/query/tool.py`.
- **API:** nos blocos `table`, `columns[].type` passa de `number` a `string` nas colunas de ano. O formato dos blocos não muda.
- **Documentação:** seção do contrato de blocos no `README.md`.
- **Bancos externos:** não toca.
- **Segredos:** não toca.
- **Endpoints sem autenticação:** nenhum endpoint novo.
