# Proposal

## Why

Depois de uma resposta, a pessoa precisa pensar sozinha no próximo passo. As sugestões só existem na tela vazia, e quem não conhece as fontes não sabe o que mais pode perguntar.

## What Changes

- **Novo bloco `suggestions`:** até 3 perguntas curtas de continuação, no fim de respostas que consultaram dados. Clientes antigos ignoram o bloco, como manda o contrato.
- **Geração barata:** uma chamada ao nível `fast`, depois da resposta e antes de gravar. Falha, demora ou saída inválida não derrubam a resposta: o bloco só não vem.
- **Quando não aparece:** em respostas sem consulta e quando a pergunta atual é a última permitida na conversa.
- **Fora do histórico:** o bloco não volta ao modelo nas perguntas seguintes.
- **Demo:** botões abaixo da última resposta. Clicar envia a pergunta.

### Fora do escopo

- Validar se cada sugestão tem resposta nas fontes: a instrução orienta, mas uma sugestão pode não ter dados.
- Configurar por ambiente a quantidade de sugestões.
- Sugestões personalizadas por histórico de outras conversas.

## Capabilities

### New Capabilities

Nenhuma.

### Modified Capabilities

- `conversation-messaging`: bloco de perguntas de continuação.
- `llm-model-tiers`: uso do nível `fast` nas sugestões.
- `demo-page`: botões de continuação.

## Impact

- **Código:** `schemas.py`, `services/chat.py`, `llm/prompts.py`, `demo/app.js` e `demo/styles.css`.
- **API:** novo tipo de bloco em `content` e em `content.delta`. Clientes devem ignorar tipos desconhecidos.
- **Custo:** uma chamada a mais ao modelo por resposta com consulta, sem o contexto das fontes. Os tokens somam em `total_tokens`.
- **Testes:** `tests/test_agent_chat.py`, com modelo fake próprio para o nível `fast`.
- **Documentação:** seções **🌐 API** e **🎬 Demo** no README.
- **Bancos externos, segredos e endpoints sem autenticação:** não são tocados.
- **Dependências:** nenhuma mudança pendente.
