# Spec Delta

## ADDED Requirements

### Requirement: Interromper a geração
Durante a geração, a página SHALL oferecer um botão Parar no lugar de Enviar. Ao parar, a conexão MUST ser encerrada, a pergunta e o texto parcial MUST sair da conversa, a pergunta MUST voltar ao campo de mensagem e a página SHALL informar que nada foi gravado.

#### Scenario: Parar uma resposta em andamento
- **WHEN** o usuário clica em Parar enquanto a Maria gera a resposta
- **THEN** a geração é interrompida, a conversa não ganha mensagens e a pergunta fica no campo de mensagem

#### Scenario: Botão ao fim da resposta
- **WHEN** a resposta termina
- **THEN** o botão volta a ser Enviar

### Requirement: Tentar novamente depois de um erro
Quando o envio falhar por erro temporário, o banner SHALL oferecer "Tentar novamente", que reenvia a mesma pergunta. Erros de limite da conversa (429) e de configuração (503) MUST ficar sem o botão.

#### Scenario: Falha do modelo
- **WHEN** o stream termina com um evento `error`
- **THEN** o banner mostra o erro e o botão, e clicar nele reenvia a pergunta

#### Scenario: Limite de perguntas
- **WHEN** a API recusa a mensagem com HTTP 429
- **THEN** o banner aparece sem "Tentar novamente"
