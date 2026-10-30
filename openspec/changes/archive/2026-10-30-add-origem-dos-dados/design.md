# Design

## Context

Motivação em `proposal.md`. Estado atual:

- **`QueryResult`:** guarda `source` (identificador da fonte, ou `fomento+simcc`), `sql`, colunas, linhas e `truncated`. Não guarda nome da fonte, descrição, data nem cobertura.
- **`QueryRunner`:** conhece `datasource.name`, o `purpose` e, entre fontes, `executed.coverage`. Quando disponível, a cobertura traz `source`, `target`, `keys` e `found`.
- **`sanitize_purpose`:** cria a descrição padrão e recusa texto que começa com SQL, mas não mascara dados pessoais. O mascaramento fica em `sanitize_untrusted_text`.
- **Blocos:** `show_chart` e `show_table` montam dicionários, e `ChartBlock` e `TableBlock` validam na leitura.
- **Atividade:** o evento `activity` não é gravado.

## Goals / Non-Goals

**Goals:**
- A origem não depende do modelo lembrar de citar a fonte.
- Mensagens gravadas seguem válidas, sem migração.

**Non-Goals:**
- Dizer quando os dados foram atualizados na origem: `queried_at` é o momento da consulta.

## Decisions

### D1. Origem registrada no resultado da consulta

`QueryResult` ganha `origin: dict | None`, preenchido por `ResultStore.add`. `show_chart` e `show_table` copiam esse valor para o bloco, então cada bloco leva a origem da consulta que usou.

Descartada: o modelo informar a fonte em `show_*`. Ele poderia errar ou omitir, e a origem é justamente o dado que precisa ser confiável.

### D2. Modelo `BlockOrigin` no contrato

`schemas.py` ganha `BlockOrigin` (`sources: list[str]`, `description: str`, `queried_at: datetime`, `coverage: BlockCoverage | None`) e `BlockCoverage` (`keys: int`, `found: int`). `ChartBlock` e `TableBlock` ganham `origin: BlockOrigin | None = None`.

Descartada: reaproveitar o dicionário `coverage` da ferramenta. Ele traz `source`, `target` e `reason`, detalhes da ligação que não interessam a quem lê.

### D3. Descrição mascarada e gravada

A descrição é `sanitize_untrusted_text(sanitize_purpose(purpose, nomes))`. Assim um dado pessoal citado na pergunta não fica gravado no bloco.

Descartada: mudar `sanitize_purpose`, que também alimenta o evento `activity`, fora do escopo desta mudança.

### D4. SQL fora do bloco

O bloco leva nomes de fontes, descrição, data e cobertura. Para evitar nomes técnicos na descrição, os campos `purpose` das ferramentas pedem linguagem de quem lê.

Descartada: mostrar o SQL num painel. Expõe a estrutura dos bancos sem autenticação, e quem audita já tem os traces.

### D5. Rodapé montado no cliente

Um helper `originFooter(origin)` em `demo/app.js`, usado por `blockRenderers.chart` e `table`, junta as partes com ` · `, como `Fonte: Fomento à Pesquisa · Bolsas por ano · consultado em 30/10/2026`. A cobertura vira `1 de 19 encontrados`. O aviso de dados cortados fica antes do rodapé.

Descartada: texto pronto no bloco. Cada cliente perderia o controle de formato, data e idioma.

## Risks / Trade-offs

- [Risco] A descrição vinda do modelo ficar imprecisa ou técnica → A instrução da ferramenta orienta, e a fonte e a data são sempre do sistema.
- [Risco] Nome de tabela aparecer na descrição → Só afeta a apresentação; a regra pede linguagem de quem lê, sem validação automática.
- [Risco] Cada bloco grava alguns campos a mais → Volume pequeno frente às linhas de dados.
