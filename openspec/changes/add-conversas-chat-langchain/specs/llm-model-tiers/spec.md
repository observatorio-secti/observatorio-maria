# Spec Delta

## Purpose

Mantém três modelos de linguagem disponíveis ao mesmo tempo, em níveis rápido, médio e avançado, configuráveis sem alteração de código e independentes do provedor.

## ADDED Requirements

### Requirement: Três níveis simultâneos
O sistema SHALL manter sempre três níveis de modelo disponíveis, `fast`, `medium` e `advanced`, utilizáveis ao mesmo tempo por mensagens diferentes.

#### Scenario: Níveis distintos na mesma conversa
- **WHEN** o usuário envia uma mensagem com `fast` e, em seguida, outra com `advanced`
- **THEN** cada resposta é gerada pelo modelo do nível solicitado

### Requirement: Configuração por ambiente
Cada nível SHALL ser configurado por variáveis de ambiente que indicam provedor e modelo (`provedor:modelo`) e parâmetros adicionais do modelo, sem mudança de código. Por padrão, os três níveis MUST usar `openai:gpt-6-luna` com raciocínio reduzido.

#### Scenario: Troca de modelo por configuração
- **WHEN** a variável do nível `advanced` é alterada para outro modelo e a aplicação é reiniciada
- **THEN** as respostas do nível `advanced` passam a usar o novo modelo e `model_name` reflete o novo valor

### Requirement: Listar níveis disponíveis
O sistema SHALL expor `GET /models` com a lista de níveis, contendo para cada um `tier` e `model_name`, sem expor credenciais.

#### Scenario: Consulta dos níveis
- **WHEN** o cliente envia `GET /models`
- **THEN** o sistema responde 200 com os níveis `fast`, `medium` e `advanced` e o modelo de cada um
