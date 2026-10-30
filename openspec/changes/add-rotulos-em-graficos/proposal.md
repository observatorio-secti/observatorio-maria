# Proposal

## Why

Gráficos e tabelas mostram nomes crus de colunas, como `total_bolsas` e `ano_inicio`, e o campo `unit` das séries nunca é preenchido. Quem lê precisa adivinhar o que cada eixo significa. Isso apareceu na verificação de `fix-explicacao-de-graficos`, em que o gráfico tinha explicação, mas legenda e eixos seguiam técnicos.

## What Changes

- **Rótulos pedidos pelo modelo:** `show_chart` e `show_table` aceitam `labels` opcional, de coluna para rótulo. Vale para o eixo `x`, as séries e as colunas da tabela.
- **Unidades:** `show_chart` aceita `units` opcional, de série para unidade (ex.: `bolsas`, `R$`), preenchendo `unit` no bloco.
- **Reserva legível:** coluna sem rótulo usa a chave com `_` trocado por espaço e inicial maiúscula (`total_bolsas` vira `Total bolsas`).
- **Pedido tolerante:** rótulo ou unidade de coluna fora do bloco é ignorado, sem recusar a visualização.
- **Instrução do modelo:** nova regra pedindo rótulos legíveis em português e unidade quando ela for conhecida. Unidade sem base nos dados ou no catálogo não deve ser inventada.
- **Demo:** o eixo Y mostra um título quando o gráfico tem uma só série ou quando todas têm a mesma unidade.

### Fora do escopo

- Copiar rótulos do catálogo: colunas calculadas não têm rótulo, e `AS total_bolsas` não aponta para a coluna de origem.
- Formatação de números e de anos nos eixos e nas tabelas (issue #6).
- Mudar `series` ou `columns` para objetos.

## Capabilities

### New Capabilities

Nenhuma.

### Modified Capabilities

- `conversation-messaging`: gráficos e tabelas com rótulos, unidades e reserva legível, e regra na instrução do modelo.
- `demo-page`: título do eixo Y nos gráficos.

## Impact

- **Código:** `query/tool.py`, `services/chat.py` (repasse dos argumentos), `llm/prompts.py` e `demo/app.js`.
- **API:** contrato igual. `label` e `unit` já existem nos blocos e mudam só de conteúdo. Mensagens gravadas não mudam.
- **Testes:** `tests/test_agent_chat.py`.
- **Documentação:** seção de blocos em **🌐 API** no README.
- **Bancos externos, segredos e endpoints sem autenticação:** não são tocados.
- **Dependências:** nenhuma mudança pendente; `fix-explicacao-de-graficos` já foi arquivada.
