# Tasks

## 1. Montagem da resposta

- [x] 1.1 Criar `services/assembly.py` com `ContentDelta` e `ResponseAssembler` (D2, D3, D4, D5). Testes em `tests/test_response_assembly.py`: dois blocos intercalados, bloco não citado, bloco inexistente, marcador repetido, marcador dividido em todos os pontos, colchetes comuns e blocos vazios.
- [x] 1.2 Usar `ResponseAssembler` em `stream_message`, com a resposta sem marcadores igual à de hoje. Testes em `tests/test_agent_chat.py`: ordem em `content`, deltas com `index` crescente e sem marcador. Atualizar **🌐 API** e **Estrutura de diretórios** no README.
- [x] 1.3 Em `llm/prompts.py`, acrescentar a regra do marcador. Teste: a instrução da explicação cita o formato.

## 2. Demo

- [x] 2.1 Em `demo/app.js`, montar a resposta por ordem de chegada (D6) e acrescentar texto depois do gráfico no exemplo do contrato. Atualizar a seção **🎬 Demo** do README.

## 3. Verificação integrada

- [x] 3.1 Rodar `poetry run task test` sem falhas e `openspec validate add-texto-intercalado --strict`.
- [x] 3.2 Com o modelo real, pedir dois gráficos, conferir a ordem durante e depois da geração, em desktop e a 375px, e remover depois a conversa de teste.
- [x] 3.3 Rodar `poetry run task eval -- --tag explicacao` e comparar com as rodadas anteriores.
