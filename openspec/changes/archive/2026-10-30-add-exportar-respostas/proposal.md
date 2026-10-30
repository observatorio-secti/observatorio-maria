# Proposal

## Why

Quem usa a Maria para escrever relatórios precisa levar a resposta para outro lugar, e hoje só dá para selecionar o texto na tela. Gráficos não podem ser salvos com legibilidade, e tabelas perdem a estrutura ao copiar.

## What Changes

- **Copiar resposta:** botão em cada resposta da Maria, que copia o texto em Markdown.
- **Baixar gráfico:** PNG com fundo, título e origem dos dados.
- **Baixar dados:** CSV de tabelas e gráficos, pronto para o Excel em pt-BR, com título, aviso de corte e origem nas últimas linhas.
- **Proteção do CSV:** células de texto que parecem fórmulas são neutralizadas, porque os dados vêm de terceiros.

### Fora do escopo

- Exportar pela API, em PDF ou a conversa inteira.
- Copiar gráficos e tabelas junto com o texto.

## Capabilities

### New Capabilities

Nenhuma.

### Modified Capabilities

- `demo-page`: copiar respostas e baixar gráficos e tabelas.

## Impact

- **Código:** `demo/app.js` e `demo/styles.css`.
- **API:** nenhuma mudança; tudo roda no navegador, a partir dos blocos já recebidos.
- **Documentação:** seção **🎬 Demo** no README.
- **LGPD:** os arquivos saem com os dados já visíveis na tela, com a origem junto.
- **Bancos externos, segredos e endpoints sem autenticação:** não são tocados.
- **Dependências:** nenhuma mudança pendente; `add-origem-dos-dados` já foi arquivada.
