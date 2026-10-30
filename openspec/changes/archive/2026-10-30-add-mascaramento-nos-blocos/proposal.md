# Proposal

## Why

A Maria só mascara CPF e e-mail no que vai ao modelo. `show_chart` e `show_table` copiam as linhas do resultado sem máscara, então o valor da origem fica em `messages.content`, no SSE, na API e na demo, inclusive no CSV baixado. Texto livre, como um resumo, pode conter CPF mesmo com as colunas sensíveis em `aggregate`.

## What Changes

- **Blocos mascarados na criação:** gráficos e tabelas novos nascem com CPF e e-mail mascarados, antes de entrar na fila de blocos. Banco da Maria, SSE, API, demo, CSV e saída dos traces recebem a mesma versão.
- **Valores aninhados:** o mascaramento alcança listas e objetos JSON, tanto nos blocos quanto no que vai ao modelo, que hoje só trata strings no primeiro nível.
- **Mensagens antigas ficam como estão:** decisão da pessoa usuária. Sem migração e sem máscara na leitura.

### Fora do escopo

- Reescrever ou mascarar na leitura mensagens já gravadas.
- Detectar CPF sem pontuação e sem o prefixo "CPF", ou guardado como número: a regra atual evita marcar códigos de 11 dígitos.
- Mascarar blocos de texto: o modelo só recebe valores mascarados, e a pergunta é escrita pela própria pessoa.
- Oferecer acesso ao valor original pela Maria: quem precisar consulta a fonte.

## Capabilities

### New Capabilities

Nenhuma.

### Modified Capabilities

- `data-querying`: o mascaramento preventivo passa a valer para os blocos, não só para o modelo.

## Impact

- **Código:** `query/sanitization.py`, `query/tool.py`.
- **Comportamento:** quem lê a tela deixa de ver CPF e e-mail em respostas novas, e uma célula mascarada pode repetir o mesmo rótulo num eixo de gráfico.
- **Testes:** `tests/test_agent_chat.py`, `tests/test_sanitization.py`.
- **Documentação:** seções de segurança e de blocos do README.
- **LGPD:** reduz a retenção de dados pessoais no banco da Maria a partir desta mudança. Mensagens antigas seguem com o valor gravado.
- **Bancos externos, segredos e endpoints sem autenticação:** não são tocados. A resposta dos endpoints de mensagens continua sem autenticação, agora com valores mascarados em blocos novos.
- **Dependências:** nenhuma mudança pendente.
