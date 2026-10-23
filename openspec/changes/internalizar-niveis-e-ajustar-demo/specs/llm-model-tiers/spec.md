# Spec Delta

## MODIFIED Requirements

### Requirement: Três níveis simultâneos
O sistema SHALL manter sempre três níveis de modelo disponíveis, `fast`, `medium` e `advanced`, para uso exclusivamente interno. A escolha do nível MUST ser feita pela aplicação e MUST NOT ser influenciável por clientes da API.

#### Scenario: Nível definido internamente
- **WHEN** um cliente envia uma mensagem
- **THEN** a resposta é gerada pelo nível definido pela aplicação, sem qualquer parâmetro do cliente

#### Scenario: Níveis distintos na mesma conversa
- **WHEN** o usuário envia várias mensagens na mesma conversa
- **THEN** todas são respondidas pelo nível definido internamente, sem que o cliente possa alternar entre níveis

#### Scenario: Níveis não expostos
- **WHEN** um cliente consulta qualquer endpoint da API ou o esquema OpenAPI
- **THEN** nenhum nível ou nome de modelo é exposto

### Requirement: Configuração por ambiente
Cada nível SHALL ser configurado por variáveis de ambiente que indicam provedor e modelo (`provedor:modelo`) e parâmetros adicionais do modelo, sem mudança de código. Por padrão, os três níveis MUST usar `openai:gpt-6-luna` com raciocínio reduzido.

#### Scenario: Troca de modelo por configuração
- **WHEN** a variável do nível `medium` é alterada para outro modelo e a aplicação é reiniciada
- **THEN** as respostas geradas pelo nível `medium` passam a usar o novo modelo, registrado internamente na mensagem

## REMOVED Requirements

### Requirement: Listar níveis disponíveis
**Reason**: Os níveis são um detalhe interno de orquestração e não devem ser visíveis nem customizáveis por clientes.
**Migration**: Remover chamadas a `GET /models`. O frontend não precisa conhecer os modelos.
