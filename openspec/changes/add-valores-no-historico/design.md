# Design

## Context

Motivação em `proposal.md`. `blocks_to_text` resume os blocos com `summarize_chart` e `summarize_table`. Os blocos gravados guardam `QueryResult.rows` sem mascarar: só as linhas enviadas ao modelo passam por `sanitize_untrusted_text`. `format_untrusted_data_xml` monta a quarentena e aplica essa sanitização a cada célula.

## Goals / Non-Goals

**Goals:**
- Responder perguntas de acompanhamento sem nova consulta, quando os dados bastam.
- Nenhum valor do histórico chega ao modelo sem quarentena e mascaramento.

**Non-Goals:**
- Comprimir o histórico ou escolher linhas relevantes.

## Decisions

### D1. Reaproveitar `format_untrusted_data_xml`

Depois do resumo, o bloco traz o XML de quarentena com `rows[:HISTORY_MAX_ROWS]`, e `truncated` fica verdadeiro quando há mais linhas.

Descartada: texto simples junto do resumo. Abriria um caminho para dados de terceiros chegarem ao modelo fora da quarentena.

### D2. Limite por linhas e por célula

`HISTORY_MAX_ROWS` limita linhas. Um limite fixo de 200 caracteres, aplicado depois de `sanitize_untrusted_text`, evita que colunas de resumo inflem o contexto. Mascarar antes de cortar impede que um CPF cortado escape do padrão.

Descartada: limite só por linhas. Vinte resumos de projeto chegariam a 40 mil caracteres.

### D3. Configuração em `Settings`

`to_langchain_message` recebe o limite vindo de `self.settings`. Zero mantém só o resumo.

Descartada: constante no código. O custo depende das fontes e precisa de ajuste sem deploy de código.

### D4. Regra do modelo prefere dado completo

O modelo usa os valores do histórico se forem completos. Com `truncated` verdadeiro, consulta de novo antes de afirmar totais ou rankings.

Descartada: sempre consultar. Manteria o custo que esta mudança quer reduzir.

## Risks / Trade-offs

- [Risco] Mais tokens em conversas com várias tabelas → Teto de 20 linhas e 200 caracteres, além de `CONVERSATION_TOKEN_CEILING` e do limite de perguntas.
- [Risco] O modelo usar número velho quando os dados mudaram → Os valores são os da própria conversa, e a origem mostra a data da consulta.
- [Risco] Bloco antigo sem `origin` → A quarentena usa uma fonte genérica, "conversa".
