# Tasks

## 1. Serviço

- [x] 1.1 Refatorar `ChatService` em `stream_message` (gerador de `UserMessageCreated`, `ContentDelta` e `AssistantMessageCompleted`, com `astream`, persistência no fim e span gerenciado por passo), com `send_message` consumindo esse gerador; verificar que a suíte atual (envio comum, 502, título, contexto e telemetria) continua passando

## 2. API

- [x] 2.1 Criar `ContentDeltaPublic` e `StreamError` e o endpoint `POST /conversations/{id}/messages/stream` com `EventSourceResponse`; verificar com testes de ordem dos eventos, concatenação dos deltas, persistência com os mesmos ids, 404/422 antes do stream e evento `error` sem persistência
- [x] 2.2 Verificar a interrupção pelo cliente (fechar o stream após o primeiro delta não grava mensagens) e a telemetria em streaming (saída do `maria.chat`, tokens e duração) com testes em memória

## 3. Demo

- [x] 3.1 Consumir o endpoint de streaming na demo (parser SSE, indicador até o primeiro delta, Markdown progressivo e substituição pela versão persistida); verificar no navegador com o modelo real

## 4. Documentação

- [x] 4.1 Reescrever o README com o estado completo do sistema (funcionalidades, arquitetura, API e eventos SSE, configuração, banco, observabilidade, demo, testes e fluxo OpenSpec); verificar `task test` sem falhas
