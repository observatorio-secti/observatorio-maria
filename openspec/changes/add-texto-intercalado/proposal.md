# Proposal

## Why

Todo o texto vem antes dos blocos. Em respostas com mais de uma visualização, a explicação fica longe do que explica, e a pessoa precisa subir e descer a tela. Com a chamada dedicada à explicação, o modelo já escreve depois de conhecer os blocos e pode dizer onde cada um entra.

## What Changes

- **Marcador de posição:** o modelo escreve `[[bloco:N]]` no texto final, usando o `block_index` devolvido por `show_chart` e `show_table`.
- **Divisão no servidor:** o texto vira vários blocos `text`, com os blocos citados entre eles. Blocos não citados vão para o fim, e marcadores inválidos são removidos.
- **Streaming:** o texto que pode ser um marcador é retido até se decidir, e cada bloco é emitido na sua posição.
- **Demo:** a resposta é montada por ordem de chegada, sem redesenhar os gráficos a cada fragmento.

### Fora do escopo

- Colocar blocos no meio de uma tabela ou lista em Markdown: o marcador divide o texto onde estiver.
- Marcadores em texto escrito antes do pedido do bloco: são removidos.
- Mudar `observatorio-front`, que deve montar a resposta pela ordem de `content`.

## Capabilities

### New Capabilities

Nenhuma.

### Modified Capabilities

- `conversation-messaging`: texto intercalado, marcadores e ordem dos blocos.
- `demo-page`: resposta montada por ordem de chegada.

## Impact

- **Código:** novo `services/assembly.py`, `services/chat.py`, `llm/prompts.py` e `demo/app.js`.
- **API:** `content` pode ter vários blocos `text`, e os blocos podem chegar antes de textos no streaming. Clientes que tratam só o primeiro `text` precisam seguir a ordem da lista. Sem marcador, a ordem continua a de hoje.
- **`observatorio-front`:** precisa renderizar `content` em ordem e aplicar `content.delta` pelo `index`.
- **Testes:** novo `tests/test_response_assembly.py` e `tests/test_agent_chat.py`.
- **Documentação:** seções **🌐 API**, **🎬 Demo** e **Estrutura de diretórios** no README.
- **Bancos externos, segredos e endpoints sem autenticação:** não são tocados.
- **Dependências:** nenhuma mudança pendente; `fix-explicacao-de-graficos` já foi arquivada.
