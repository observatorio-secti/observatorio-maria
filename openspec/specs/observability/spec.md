# observability Specification

## Purpose
Torna o comportamento da API e da IA observável em padrão aberto (OpenTelemetry): traces, métricas e logs correlacionados, além da análise dos passos do LLM, sem depender de serviços pagos.

## Requirements

### Requirement: Traces de requisição ponta a ponta
O sistema SHALL emitir traces OpenTelemetry via OTLP em que uma requisição HTTP, suas consultas ao banco e as chamadas ao LLM aparecem no mesmo trace.

#### Scenario: Envio de mensagem rastreado
- **WHEN** um cliente envia uma mensagem a uma conversa
- **THEN** é emitido um trace com o span HTTP da rota, spans das consultas ao banco e o span do LLM como descendente

### Requirement: Caminho da IA por resposta
Cada resposta da Maria, completa ou em streaming, SHALL gerar um span de cadeia `maria.chat` no padrão OpenInference, com entrada, saída e o identificador da conversa como sessão, contendo como filhos os spans das chamadas ao modelo, com mensagens, modelo e contagem de tokens.

#### Scenario: Inspeção de uma resposta
- **WHEN** a Maria responde a uma mensagem
- **THEN** existe um span `maria.chat` com `session.id` igual ao id da conversa e um span filho do LLM com as mensagens enviadas, a resposta e os tokens

#### Scenario: Falha do modelo rastreada
- **WHEN** o modelo falha durante a geração
- **THEN** o span `maria.chat` termina com status de erro e a exceção registrada

#### Scenario: Resposta em streaming rastreada
- **WHEN** a Maria responde pelo endpoint de streaming
- **THEN** o span `maria.chat` tem como saída o texto completo, e as métricas de tokens e duração são registradas como numa resposta completa

### Requirement: Métricas de uso do LLM
O sistema SHALL registrar as métricas `gen_ai.client.token.usage` (por tipo de token: entrada e saída) e `gen_ai.client.operation.duration`, com o modelo como atributo, seguindo as convenções semânticas GenAI do OpenTelemetry.

#### Scenario: Tokens contabilizados
- **WHEN** o modelo responde informando 12 tokens de entrada e 5 de saída
- **THEN** `gen_ai.client.token.usage` registra 12 com `gen_ai.token.type=input` e 5 com `gen_ai.token.type=output`

### Requirement: Métricas HTTP
O sistema SHALL emitir métricas de duração das requisições HTTP por rota e status, segundo as convenções semânticas HTTP do OpenTelemetry.

#### Scenario: Requisição medida
- **WHEN** um cliente chama `GET /conversations`
- **THEN** a métrica de duração de requisições HTTP é registrada com a rota `/conversations` e o status 200

### Requirement: Logs correlacionados
Os logs da aplicação SHALL ser exportados via OTLP com `trace_id` e `span_id` quando emitidos dentro de um trace.

#### Scenario: Log de falha do modelo
- **WHEN** o modelo falha e a aplicação registra o erro
- **THEN** o registro de log carrega o `trace_id` do trace da requisição

### Requirement: Configuração padrão e desligamento
A telemetria SHALL ser configurada pelas variáveis padrão `OTEL_*` (serviço, endpoint OTLP) e MUST ser completamente desligável com `OTEL_SDK_DISABLED=true`, sem alterar o comportamento da API.

#### Scenario: Telemetria desligada
- **WHEN** a aplicação inicia com `OTEL_SDK_DISABLED=true`
- **THEN** nenhum provedor de telemetria é configurado e todos os endpoints funcionam normalmente

#### Scenario: Coletor indisponível
- **WHEN** a telemetria está ligada e o coletor está fora do ar
- **THEN** as requisições continuam respondendo normalmente

### Requirement: Ocultação de conteúdo
O sistema SHALL permitir ocultar o conteúdo das mensagens nos spans de LLM por configuração (variáveis do OpenInference), mantendo a estrutura do trace, modelo, tokens e latência.

#### Scenario: Conteúdo oculto
- **WHEN** a aplicação roda com `OPENINFERENCE_HIDE_INPUTS=true` e `OPENINFERENCE_HIDE_OUTPUTS=true`
- **THEN** os spans de LLM não contêm o texto das mensagens, mas mantêm modelo e tokens

### Requirement: Stack local de observabilidade
O projeto SHALL fornecer uma stack local via Docker Compose em que os traces chegam ao Tempo, os traces de LLM ao Phoenix, as métricas ao Prometheus e os logs ao Loki, todos visualizáveis no Grafana com navegação entre trace e logs.

#### Scenario: Stack em execução
- **WHEN** o desenvolvedor sobe a stack e envia uma mensagem pela API
- **THEN** o trace aparece no Tempo e no Phoenix, as métricas no Prometheus e os logs no Loki, e do trace no Grafana é possível abrir os logs correspondentes

### Requirement: Consultas rastreadas
Cada consulta pedida pelo modelo SHALL gerar um span de ferramenta no padrão OpenInference, filho de `maria.chat`, com a fonte, o SQL recebido, o resultado (linhas devolvidas e truncamento) ou o motivo da recusa. O conteúdo SQL e das linhas MUST seguir a mesma configuração de ocultação das mensagens.

#### Scenario: Consulta no trace
- **WHEN** a Maria executa duas consultas e responde
- **THEN** o span `maria.chat` tem como filhos as chamadas ao modelo e dois spans de ferramenta com o SQL e o número de linhas

#### Scenario: Conteúdo oculto
- **WHEN** a ocultação de conteúdo está ligada
- **THEN** os spans de ferramenta mantêm fonte, duração e status, sem o SQL nem as linhas

#### Scenario: Recusa rastreada
- **WHEN** uma consulta é recusada na validação
- **THEN** o span de ferramenta registra o motivo e não há span de banco na origem

### Requirement: Métricas do agente
O sistema SHALL registrar, por resposta, o número de chamadas ao modelo (`maria.agent.model_calls`) e, por consulta, o desfecho (`maria.query.count` com `outcome` igual a `executed`, `rejected`, `failed` ou `timeout`) e a fonte.

#### Scenario: Contagem por desfecho
- **WHEN** uma resposta tem uma consulta recusada e outra executada
- **THEN** `maria.query.count` registra uma ocorrência `rejected` e uma `executed`, e `maria.agent.model_calls` registra o número de chamadas da resposta
