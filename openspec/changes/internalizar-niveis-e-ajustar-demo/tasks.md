# Tasks

## 1. Níveis internos

- [x] 1.1 Remover `routers/models.py`, `ModelPublic`/`ModelList` e a rota no `app.py`; ajustar `test_models.py` (manter testes do builder e do 503) e verificar que `/models` responde 404
- [x] 1.2 `MessageCreate` só com `content` e `extra='forbid'`; remover `model_tier`/`model_name` de `MessagePublic`; verificar com testes de 422 para `model` e ausência dos campos nas respostas e no OpenAPI
- [x] 1.3 `ChatService` usa `CHAT_MODEL_TIER` interno e continua gravando `model_tier`/`model_name` no banco; verificar com teste que lê a mensagem do banco

## 2. Demo

- [x] 2.1 Extrair `mount_demo(app, settings)` e testar demo habilitada (200) e desabilitada (404)
- [x] 2.2 Habilitar envio imediato (criação automática da conversa), indicador "Maria está respondendo…" e bloqueio de envio duplo; remover seletor de nível, pílula de modelos e aba Endpoints; verificar no navegador contra a API real
- [x] 2.3 Atualizar o README (endpoints, contrato de envio e demo) e verificar `task test` sem falhas
