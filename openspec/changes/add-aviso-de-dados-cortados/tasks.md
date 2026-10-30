# Tasks

## 1. Indicação nos blocos

- [x] 1.1 Acrescentar `truncated: bool = False` a `ChartBlock` e `TableBlock` em `schemas.py` (D1) e preencher a partir de `QueryResult.truncated` em `show_chart` e `show_table`. Testes em `tests/test_agent_chat.py`: resultado cortado marca os dois blocos, resultado completo fica falso, e mensagem gravada sem o campo volta como falso pela API. Atualizar a seção de blocos em **🌐 API** no README.
- [x] 1.2 Em `llm/prompts.py`, acrescentar a regra de dados cortados. Teste: o prompt de sistema contém as três orientações.

## 2. Demo

- [x] 2.1 Em `demo/app.js`, criar `truncationNotice` (D3) e usá-lo em `blockRenderers.chart` e `table`, com estilo discreto em `demo/styles.css`. Atualizar a seção **🎬 Demo** do README.

## 3. Verificação integrada

- [x] 3.1 Rodar `poetry run task test` sem falhas e `openspec validate add-aviso-de-dados-cortados --strict`.
- [x] 3.2 Com o modelo real, fazer uma pergunta que corte o resultado (ex.: listar todos os projetos sobre educação), conferir o aviso e o texto do modelo em desktop e a 375px, reabrir a conversa e removê-la depois.

## Workflow follow-up

- Arquivar com `/opsx:archive`, nos commits `docs(openspec): planeja`, `feat:` e `docs(openspec): arquiva`, sem incluir a alteração local de `.env.example`.
