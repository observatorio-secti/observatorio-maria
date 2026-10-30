# Design

## Context

`QueryRunner` guarda no `ResultStore` as linhas sem máscara e entrega ao modelo uma cópia sanitizada. `show_chart` e `show_table` montam os blocos a partir do `ResultStore`. O bloco então segue para o SSE e para `messages.content`, de onde a API e a demo leem. O histórico já mascara ao reler os blocos.

## Goals / Non-Goals

**Goals:**

- Nenhum bloco novo sai com CPF ou e-mail reconhecíveis, em nenhuma saída.
- Um único ponto de mascaramento para todas as saídas.

**Non-Goals:**

- Tratar mensagens antigas ou ampliar os padrões reconhecidos.

## Decisions

### D1. Mascarar o bloco inteiro ao montá-lo

`show_chart` e `show_table` passam o bloco pronto por `mask_value` antes de `pending_blocks`. Assim, título e rótulos escritos pelo modelo também são cobertos, e o SSE e a gravação herdam o resultado.

Alternativa descartada: mascarar só `data` e `rows`. O modelo pode repetir no título um CPF digitado na pergunta. Mascarar ao gravar e ao emitir, em dois pontos, também foi descartado: um novo caminho de saída poderia esquecer a máscara.

### D2. `ResultStore` continua com os valores da origem

A avaliação com perguntas de referência compara `result.rows` com o esperado, e blocos só leem desse armazenamento em memória, que dura uma resposta.

Alternativa descartada: mascarar no `ResultStore`. Mudaria a avaliação sem ganho, porque o armazenamento não é uma saída.

### D3. Bloco usa `mask_pii`, não `sanitize_untrusted_text`

O escape de delimitadores e o corte em 2.000 caracteres existem para o contexto do modelo. Na tela, o escape mostraria `&lt;` literal e o corte esconderia texto que hoje aparece inteiro.

Alternativa descartada: reusar `sanitize_untrusted_text`. Mudaria a exibição de textos longos sem relação com privacidade.

### D4. Mascaramento recursivo, com chaves

`mask_value` percorre listas e objetos, porque `serialize_value` preserva arrays e JSON da origem. Chaves de objetos também são mascaradas, para `columns[].key` e `x.key` continuarem batendo com as chaves de `rows` e `data`. `sanitize_untrusted_text` ganha a mesma recursão, fechando a mesma lacuna no contexto do modelo.

Alternativa descartada: converter listas e objetos em string antes de mascarar. Mudaria o tipo entregue ao cliente.

### D5. Mensagens antigas ficam como estão

Decisão da pessoa usuária. O histórico já as mascara para o modelo, e reapresentá-las por `show_table` ou `show_chart` gera um bloco novo, mascarado.

Alternativa descartada: máscara na leitura, que acrescenta custo permanente, ou migração de dados, que é irreversível.

## Risks / Trade-offs

- [Risco] Mensagens antigas seguem com CPF e e-mail no banco e na tela → Registrado como decisão. Uma mudança própria pode tratá-las se a política mudar.
- [Risco] CPF sem pontuação, sem prefixo ou numérico não é reconhecido → Limite já existente do padrão, documentado no README. Colunas de identificadores devem usar `aggregate` no catálogo.
- [Risco] Valores distintos viram o mesmo rótulo num eixo → Aceito: agrupar por CPF ou e-mail não é uso previsto de um gráfico.
- [Risco] Texto escrito pelo modelo não é mascarado → O modelo só recebe valores mascarados. Um CPF digitado na pergunta pode ser repetido, e a pessoa já o conhece.
