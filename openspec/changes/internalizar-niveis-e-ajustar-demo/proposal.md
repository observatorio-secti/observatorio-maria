# Proposal

## Why

Os níveis de modelo (rápido, médio e avançado) são um recurso interno de orquestração. Hoje eles vazam para fora: o cliente escolhe o nível por mensagem, `GET /models` os lista e as mensagens expõem `model_tier`/`model_name`. Isso deixa o comportamento manipulável externamente e acopla o frontend a um detalhe de implementação. Além disso, na demo o campo de mensagem nasce desabilitado, então na prática não dá para enviar mensagens.

## What Changes

- **BREAKING** Remoção do endpoint `GET /models`.
- **BREAKING** `POST /conversations/{id}/messages` passa a aceitar apenas `content`; qualquer campo extra (incluindo `model`) é rejeitado com 422. O nível é escolhido internamente pela aplicação.
- **BREAKING** As mensagens retornadas pela API deixam de expor `model_tier` e `model_name`. Os valores continuam gravados no banco para uso interno (auditoria e observabilidade).
- A demo permite digitar e enviar logo ao abrir a página: sem conversa selecionada, o envio cria uma conversa automaticamente.
- A demo mostra um indicador enquanto a Maria gera a resposta e não exibe nenhum detalhe de modelo.
- Remoção da aba "Endpoints" da demo.

## Capabilities

### New Capabilities
- `demo-page`: página de demonstração servida pela própria API para apresentar as funcionalidades a usuários e à gestão.

### Modified Capabilities
- `llm-model-tiers`: os níveis passam a ser exclusivamente internos; remoção da listagem pública.
- `conversation-messaging`: envio sem escolha de nível e histórico sem metadados de modelo.

## Impact

- API: remoção de `/models`, mudança no corpo de envio e no formato das mensagens.
- Código: `routers/models.py` (removido), `schemas.py`, `services/chat.py`, `routers/conversations.py`, `app.py`, `demo/`.
- Testes: `test_models.py`, `test_messages.py`.
- Banco: sem mudança de esquema.
