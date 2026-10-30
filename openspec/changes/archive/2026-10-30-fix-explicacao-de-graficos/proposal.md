# Proposal

## Why

Gráficos e tabelas chegam sem explicação. Depois de `show_chart` ou `show_table`, a geração termina sem voltar ao modelo, e a regra de evitar texto durante as consultas desencoraja escrever antes. Pelo mesmo motivo, um gráfico recusado por coluna inexistente some sem o modelo receber o motivo, o que a spec já exige. É a primeira história do plano de conversa mais agradável, e as demais se apoiam nela.

## What Changes

- **Volta ao modelo depois da apresentação:** quando todos os pedidos de `show_chart` e `show_table` dão certo, a geração faz mais uma chamada, sem ferramentas, para escrever a explicação.
- **Pedido recusado:** o modelo recebe o motivo e a chamada seguinte mantém as ferramentas, para corrigir o pedido enquanto houver orçamento.
- **Última chamada só com texto:** a última chamada do orçamento deixa de oferecer ferramentas, o que garante o texto final mesmo com o orçamento no limite.
- **Instrução do modelo:** nova regra pedindo que a explicação diga o que a visualização mostra, o principal destaque e as ressalvas, só com números dos resultados, e que nada seja escrito na chamada que pede a visualização.
- **Sem texto repetido:** a chamada da explicação é orientada a não repetir o que já foi escrito, e textos de chamadas diferentes são separados por um parágrafo.
- **Resposta só com blocos:** continua aceita, mas como exceção, para quando o modelo não devolver texto.

### Fora do escopo

- Rótulos e unidades dos gráficos (`add-rotulos-em-graficos`).
- Texto intercalado com os blocos (`add-texto-intercalado`): a explicação continua vindo antes dos blocos.
- Reservar a penúltima chamada para apresentação: ela tiraria uma rodada de consulta de toda resposta longa.
- Mudanças na demo: o contrato de blocos e o streaming não mudam.

## Capabilities

### New Capabilities

Nenhuma.

### Modified Capabilities

- `conversation-messaging`: última chamada sem ferramentas, ordem dos blocos com a explicação como padrão e novos requisitos de explicação e de recusa de visualização.

## Impact

- **Código:** `services/chat.py` (loop de geração), `query/tool.py` (remove `build_presentation_tools`, que fica sem uso) e `llm/prompts.py`.
- **Testes:** `tests/test_agent_chat.py`, inclusive os testes que hoje esperam o fim da resposta logo depois de `show_*`.
- **Custo:** respostas com gráfico ou tabela gastam uma chamada a mais ao modelo, dentro de `MARIA_AGENT_MAX_MODEL_CALLS`. Com fomento e Simcc, cada chamada leva o contexto das fontes.
- **Evals:** novas perguntas com critério `judge` em `evals/reference.yaml`.
- **API e demo:** sem mudança de contrato. O texto final passa a chegar em mais respostas com blocos.
- **Bancos externos, segredos e endpoints sem autenticação:** não são tocados.
- **Dependências:** nenhuma outra mudança pendente.
