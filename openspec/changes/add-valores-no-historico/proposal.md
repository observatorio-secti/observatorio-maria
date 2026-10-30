# Proposal

## Why

O histórico guarda só título e contagem de gráficos e tabelas. Perguntas como "qual foi o maior?" obrigam a Maria a consultar tudo de novo, ou ela fica sem os números. Cada resposta custa dezenas de milhares de tokens, e a repetição deixa a conversa lenta.

## What Changes

- **Valores no histórico:** até `HISTORY_MAX_ROWS` linhas (padrão 20) de cada visualização anterior vão ao modelo, com o total de linhas.
- **Quarentena obrigatória:** esses valores entram em `<untrusted_database_data>`, com mascaramento de CPF e e-mail e escape de delimitadores, porque os blocos gravados não são mascarados.
- **Limite por célula:** textos longos do histórico são cortados em 200 caracteres.
- **Instrução do modelo:** usar os valores quando bastarem, e consultar de novo quando forem parciais.
- **Desligável:** `HISTORY_MAX_ROWS=0` volta ao comportamento atual.

### Fora do escopo

- Gerar gráficos a partir de resultados anteriores: entra com `add-reuso-de-resultados`.
- Mascarar os blocos gravados e exibidos na tela: o comportamento atual é de outro requisito e fica para uma mudança própria.
- Resumir conversas longas.

## Capabilities

### New Capabilities

Nenhuma.

### Modified Capabilities

- `conversation-messaging`: valores das visualizações no histórico, quarentena e uso pelo modelo.

## Impact

- **Código:** `services/chat.py`, `settings.py`, `llm/prompts.py`.
- **Configuração:** `HISTORY_MAX_ROWS` no `.env.example` e na tabela do README.
- **Custo:** mais tokens por pergunta seguinte, limitados pelo teto de linhas, em troca de menos consultas repetidas.
- **Testes:** `tests/test_agent_chat.py`.
- **LGPD:** dados voltam ao modelo só pela quarentena e com mascaramento.
- **Bancos externos, segredos e endpoints sem autenticação:** não são tocados.
- **Dependências:** nenhuma mudança pendente.
