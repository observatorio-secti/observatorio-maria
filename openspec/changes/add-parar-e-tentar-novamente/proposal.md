# Proposal

## Why

Uma resposta da Maria pode levar dezenas de segundos, e hoje não há como interrompê-la. Quando a geração falha, a pessoa precisa reenviar a pergunta por conta própria, a partir do banner de erro.

## What Changes

- **Parar:** durante a geração, o botão Enviar vira Parar. Interromper fecha a conexão, e a API descarta a resposta sem gravar nada, como já faz.
- **Pergunta preservada:** depois de parar, a pergunta continua no campo, pronta para editar.
- **Tentar novamente:** erros temporários mostram um botão no banner que reenvia a mesma pergunta.

### Fora do escopo

- Regenerar uma resposta já concluída: contaria mais uma pergunta no limite da conversa.
- Guardar a resposta parcial ao parar.
- Tentar novamente em erros que não se resolvem repetindo, como o limite de perguntas (429) e a falta de configuração do modelo (503).
- Novas rotas ou mudanças na API.

## Capabilities

### New Capabilities

Nenhuma.

### Modified Capabilities

- `demo-page`: interromper a geração e tentar novamente depois de um erro.

## Impact

- **Código:** `demo/app.js`.
- **API:** nenhuma mudança.
- **Documentação:** seção **🎬 Demo** no README.
- **Bancos externos, segredos e endpoints sem autenticação:** não são tocados.
- **Dependências:** nenhuma mudança pendente.
