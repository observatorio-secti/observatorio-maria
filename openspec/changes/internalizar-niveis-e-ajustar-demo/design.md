# Design

## Context

Os requisitos estão em `specs/` e a motivação em `proposal.md`. Hoje o `ModelRegistry` é injetado nas rotas, `MessageCreate` aceita `model` e `MessagePublic` expõe `model_tier`/`model_name`. A demo (`src/observatorio_maria/demo/`) foi criada sem spec e ganha uma agora.

## Goals / Non-Goals

**Goals:**
- A seleção do nível fica dentro do `ChatService`, num único ponto.
- O contrato público da API não contém nenhum detalhe de modelo.

**Non-Goals:**
- Roteamento inteligente entre níveis (por complexidade da pergunta, por exemplo). Fica como evolução, sem mudar a API.

## Decisions

1. **Nível do chat como constante interna.** O `ChatService` usa `CHAT_MODEL_TIER = ModelTier.MEDIUM`. Os outros níveis seguem disponíveis no registro para usos internos futuros (geração de título, roteamento, avaliação). *Alternativa:* uma variável de ambiente para o nível padrão. Descartada porque "não customizável de fora" vale também para a configuração do chat. O que a operação pode trocar é o modelo de cada nível, não qual nível o chat usa.
2. **Rejeitar campos extras.** `MessageCreate` usa `model_config = ConfigDict(extra='forbid')`. Assim o cliente recebe 422 explícito em vez de ter o campo silenciosamente ignorado, o que evitaria a falsa impressão de que a escolha funcionou.
3. **Metadados só no banco.** `Message.model_tier`/`model_name` permanecem nas colunas (auditoria e correlação com observabilidade), mas saem de `MessagePublic`.
4. **Demo.** O textarea nasce habilitado. Sem conversa atual, `sendMessage` primeiro faz `POST /conversations` e depois envia. Um balão "Maria está respondendo…" fica visível enquanto a requisição está pendente, e o botão é bloqueado durante o envio. O seletor de nível, a pílula de modelos e a aba Endpoints são removidos.
5. **Montagem condicional testável.** Para testar `DEMO_ENABLED=false`, a montagem fica numa função `mount_demo(app, settings)` chamada no `app.py`. O teste a aplica num `FastAPI()` novo.

## Risks / Trade-offs

- [Clientes existentes que enviam `model` passam a receber 422] → É a intenção (BREAKING declarado). A demo é o único cliente atual.
- [Um único nível no chat pode ser caro ou lento] → O modelo do nível é configurável por ambiente, e o roteamento entre níveis pode ser adicionado no serviço sem mudar a API.
