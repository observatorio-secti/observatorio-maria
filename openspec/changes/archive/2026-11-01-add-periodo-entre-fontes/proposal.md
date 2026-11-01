# Proposal

## Why

A Maria não consegue responder se artigos do Simcc foram publicados durante uma bolsa do fomento. O validador recusa comparar datas entre fontes, e ela atribuiu a falha a um limite de "100 currículos" que não existe: `QUERY_MAX_ROWS` corta as linhas devolvidas, não o cruzamento. Hoje a pergunta só passa com colunas calculadas em CTE, forma que perde a cobertura.

## What Changes

- Consultas entre fontes passam a aceitar `>`, `>=`, `<`, `<=` e `BETWEEN` entre colunas de data ou número de fontes diferentes, desde que a consulta use uma ligação declarada.
- Continuam recusados: igualdade fora das ligações, `<>`, `LIKE`, comparação de ordem entre colunas de texto, produto cartesiano e consulta sem ligação.
- O contexto do modelo passa a dizer que o limite de linhas vale para o que é devolvido, não para o que é cruzado, e que perguntas sobre todos os bolsistas se respondem com agregação.
- A política do conceito `pesquisadores` ganha a receita de "artigos durante a bolsa": comparação por ano, bolsa sem término, remoção de coautores repetidos e a ressalva de que vigência não prova financiamento.
- O `task eval` ganha perguntas de período entre fontes.

### Fora do escopo

- Limite maior para tabelas e exportação CSV.
- Fechar o desvio por colunas calculadas em CTE, que não têm origem rastreada e escapam da checagem entre fontes.
- Investigar a cobertura baixa da ligação (1.230 de 32.798 Lattes do fomento no Simcc).
- Citações e Qualis canônicos por bolsista: `mv_canonical_articles` não identifica o autor.
- Considerar `data_saida_pesquisador` na vigência.

## Capabilities

### New Capabilities

Nenhuma.

### Modified Capabilities

- `data-querying`: a junção entre fontes passa a aceitar comparações de ordem junto com uma ligação declarada.
- `data-catalog`: a seção "Consultas entre fontes" explica o limite, e a política de `pesquisadores` traz a receita de período.
- `answer-evaluation`: as perguntas de referência cobrem períodos entre fontes.

## Impact

- **Código:** `query/federated_validator.py`, `catalog/context.py`, `catalog/concepts.yaml`, `evals/reference.yaml`, testes e `README.md`.
- **Bancos externos:** só leitura, sem nenhuma alteração. Os testes usam fontes temporárias.
- **Segredos e endpoints:** não muda nada. Não há endpoint novo.
- **Produção:** o seed não sobrescreve conceitos existentes, então a política nova precisa ser aplicada pela API depois do deploy.
- **Dependências:** nenhuma mudança pendente.
