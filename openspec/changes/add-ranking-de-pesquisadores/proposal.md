# Proposal

## Why

Usuários criticam que a Maria lista pesquisadores sem critério. A busca temática do catálogo do Simcc (`MATCH_TEXT(r.abstract, ...) LIMIT 10`) não tem `ORDER BY`: para "dengue", devolve 10 pesquisadores quaisquer entre os 46 que citam o termo no resumo e ignora os 438 com produção sobre o tema. A V2 do simcc-back já resolve isso com um ranking por relevância sobre views materializadas atualizadas periodicamente em produção, e a Maria pode reaproveitar essas views em vez de reinventar o critério.

## What Changes

- **Nova ferramenta `search_researchers`:** recebe o termo, período, tipos de produção e instituição opcionais, e ranqueia pesquisadores do Simcc pela mesma fórmula da V2 (resumo do currículo × 1,5 + melhor produção + ln(nº de produções que casam + 1)), lendo `mv_search_documents` e `mv_researcher_search` com SQL fixo, parametrizado e somente leitura.
- **Evidências nos cards:** cada pesquisador do ranking traz quantas produções casam com o termo, por tipo, e até 3 produções (título, tipo, ano) que justificam a posição.
- **Bloco `researchers`:** novo campo opcional `ranking` (termo, critério, campos considerados e data dos dados) e campo opcional `evidence` em cada card. Blocos antigos continuam válidos.
- **Data e ausência do índice:** a data dos dados vem de `mv_refresh_metadata`. Views vazias ou ausentes fazem a ferramenta devolver erro explicado ao modelo, sem lista vazia apresentada como resposta.
- **Demo:** cards mostram as evidências e, acima da lista, um aviso de que a ordem considera só os campos textuais indexados (e não Qualis, citações ou índice h) e a data dos dados.
- **Catálogo do Simcc e prompt:** buscas temáticas de pesquisadores passam a usar `search_researchers`; o exemplo `abstract LIMIT 10` sai do seed.

### Fora do escopo

- Filtros por território, cidade, programa de pós-graduação ou coleção no ranking (as views têm os arrays; ficam para uma etapa seguinte).
- Outros critérios de ordem (Qualis, citações, índice h, recência ponderada) e escolha do critério pelo usuário.
- Trecho destacado (`ts_headline`) das evidências.
- Reserva sobre as tabelas base quando as views estiverem vazias.
- Ranking de produções e de fontes que não sejam o Simcc.
- Mudanças no simcc-back, nas views ou na rotina de refresh, e no `observatorio-front`.

## Capabilities

### New Capabilities

- `researcher-ranking`: ranking de pesquisadores do Simcc por relevância textual, com evidências, data dos dados e recusa quando o índice de busca não está disponível.

### Modified Capabilities

- `conversation-messaging`: bloco `researchers` com `ranking` e `evidence`, e uso de `search_researchers` pelo agente em buscas temáticas.
- `demo-page`: evidências nos cards e aviso sobre os campos que definem a ordem.
- `data-catalog`: instruções e exemplos do seed do Simcc para buscas temáticas de pesquisadores.

## Impact

- **Código:** novo `query/ranking.py`; `query/tool.py`, `query/cards.py`, `schemas.py`, `services/chat.py`, `llm/prompts.py`, `demo/app.js` e `demo/styles.css`.
- **API:** campos opcionais novos no bloco `researchers`; nenhum campo existente muda.
- **Catálogo:** `catalog/simcc.yaml`. Catálogos já semeados não recebem a instrução nova sozinhos; o `docs/deploy.md` explica como aplicá-la.
- **Bancos externos:** só leitura de `mv_search_documents`, `mv_researcher_search`, `mv_refresh_metadata` e `institution` no Simcc. Nada é criado, alterado ou atualizado neles, inclusive o refresh.
- **Dependência operacional:** a qualidade do ranking depende do refresh periódico das views pelo simcc-back, confirmado como confiável em produção.
- **Segredos:** não toca.
- **Endpoints sem autenticação:** nenhum endpoint novo.
- **Dependências:** nenhuma nova.
- **Mudanças em andamento:** não depende de outra mudança não arquivada.
