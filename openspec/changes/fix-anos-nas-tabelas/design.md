# Design

## Context

`infer_column_types` marca qualquer inteiro como `number`, e `show_table` grava esse tipo no bloco. A demo formata todo `number` com `toLocaleString('pt-BR')`, o que produz `2.020`. O tipo `string` já é exibido como veio, inclusive quando o valor é inteiro.

`TableColumn` já normaliza tipos de blocos antigos ao validar `MessagePublic`. O `content.delta`, porém, envia o bloco como dicionário, sem passar por essa validação. Ver proposal.md para a motivação.

## Goals / Non-Goals

**Goals:**

- Mostrar anos sem separador em blocos novos e gravados, no streaming e no histórico.
- Resolver na API, para o `observatorio-front` receber a correção sem repetir a regra.

**Non-Goals:**

- Mudar a inferência geral de tipos em `query/execution.py`, que também alimenta gráficos e federação.
- Corrigir o tipo gravado no banco: a leitura normaliza.

## Decisions

**Tipo `string` em vez de um tipo novo.** A coluna de ano é um rótulo, e o contrato já tem esse tipo. Alternativa descartada: `year` no `Literal` de `TableColumn`, porque quebraria clientes que só conhecem os três tipos atuais e pediria mudança na demo.

**Regra na API em vez da demo.** Alternativa descartada: testar o nome da coluna em `app.js`, como sugere a issue. Corrigiria só a demo, e o frontend teria de repetir a regra.

**Nome e valores juntos.** A chave precisa ter o termo exato `ano` ou `year`, e os valores precisam ser inteiros de 1900 a 2100. Alternativa descartada: só o nome, porque `valor_por_ano` perderia o separador em valores monetários. Só a faixa também foi descartada, porque contagens como 2020 parecem anos. Valores como `2020.0` contam como inteiros, já que `EXTRACT` do PostgreSQL devolve `numeric`.

**Uma regra em dois pontos.** Uma função pura em `schemas.py` decide o tipo. Um `model_validator` de `TableBlock` a aplica na leitura, onde as linhas estão disponíveis, e `show_table` a aplica ao montar o bloco, o que cobre o streaming. Alternativa descartada: validar o bloco no `to_server_sent_event`, porque o evento carrega um dicionário livre e passaria a depender do formato de cada bloco.

## Risks / Trade-offs

- [Coluna `ano` que não é ano, com valores nessa faixa] → Sem separador, o número continua correto.
- [Alinhamento] → A coluna de ano passa a ficar à esquerda, como as demais categorias. É coerente com seu papel de rótulo.
- [Alias sem o termo, como `exercicio`] → Continua formatado. O caso fica registrado como fora do escopo.
- [Ordenação ou totais por tipo em clientes] → O valor continua numérico nas linhas, e a demo não ordena por tipo.
