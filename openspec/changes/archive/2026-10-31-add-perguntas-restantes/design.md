# Design

## Context

`ChatService.check_conversation_limits` conta as mensagens do usuário e compara com `CONVERSATION_MAX_QUESTIONS`. `ConversationPublic` é compartilhado por criação, listagem, consulta e renomeação. `get_chat_service` depende do registro de modelos, então usá-lo em `GET /conversations/{id}` faria a rota depender da chave do modelo.

A demo guarda a conversa em `state.current`, relê `GET /conversations/{id}` ao abrir e ao fim de cada resposta e chama `showCurrentHeader` sempre que a conversa muda. Ver proposal.md para a motivação.

## Goals / Non-Goals

**Goals:**

- Uma só regra de contagem para a recusa e para o contador.
- Manter a listagem sem consultas adicionais.

**Non-Goals:**

- Antecipar a recusa na demo: a API continua sendo quem decide.

## Decisions

**`questions_asked` e `questions_limit` em vez de `questions_remaining`.** O cliente deriva o restante e também pode exibir o limite. Alternativa descartada: só `questions_remaining`, porque "Restam 7 de 10" exigiria o limite de qualquer forma.

**Schema `ConversationDetail` só para o `GET` por id.** Ele estende `ConversationPublic`. Alternativa descartada: adicionar os campos a `ConversationPublic`, porque a listagem faria uma contagem por conversa ou precisaria de uma agregação sem uso na demo.

**Função `count_questions(session, conversation)` em `services/chat.py`.** Ela é usada por `check_conversation_limits` e pela rota, ao lado de `get_history`, que também não usa o modelo. Alternativa descartada: um método de `ChatService`, pelo acoplamento com o modelo descrito no Context.

**`questions_limit` nulo com o limite desligado.** Alternativa descartada: devolver `0`, que para um cliente pareceria "nenhuma pergunta permitida".

**Contador dentro de `showCurrentHeader`.** A função já é chamada em todos os pontos em que a conversa muda. Uma conversa recém-criada por `POST` não traz `questions_limit`, então o contador fica oculto até a releitura ao fim da resposta. Alternativa descartada: reler a conversa logo depois do `POST`, uma requisição a mais para um estado de poucos segundos.

**Texto sem contar a pergunta em andamento.** O número muda ao fim da resposta, quando a API já gravou a pergunta. Alternativa descartada: descontar no envio, porque uma resposta interrompida não grava nada e o número teria de voltar.

## Risks / Trade-offs

- [Contagem por requisição em `GET /conversations/{id}`] → A consulta é um `count` filtrado pela conversa, o mesmo já feito a cada envio.
- [Outra aba envia uma pergunta] → O contador fica defasado até a próxima resposta; a API continua recusando com 429 e o banner explica.
- [Teto de tokens atingido antes do limite de perguntas] → O contador pode mostrar perguntas restantes enquanto a API recusa. O banner atual cobre o caso, e o teto é opcional e fica fora do escopo.
- [Layout a 375px] → O contador é uma linha curta, verificada no celular.
