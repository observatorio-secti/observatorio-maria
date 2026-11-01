# Design

## Context

A aba vive em três arquivos estáticos (`index.html`, `catalog.js`, `styles.css`), sem build, e consome a API do catálogo. No catálogo local há duas fontes, ambas ativas e sem sincronização automática: `fomento` com 12 de 18 entidades visíveis e `simcc` com 24 de 94. Todas as visíveis são consultáveis, e os 106 relacionamentos estão ligados.

A API já impõe que consultável exige visível: ocultar uma entidade zera `queryable`, e a página não precisa repetir a regra. A ferramenta `query_across_sources` só existe quando há ligação `active` entre fontes consultáveis.

## Goals / Non-Goals

**Goals:**
- Reduzir os controles à vista sem perder nenhuma capacidade da aba.
- Fazer com que todo estado desligado relevante mostre como ligar.

**Non-Goals:**
- Mudar API, esquema ou contexto do modelo.
- Criar sistema de componentes, build ou nova dependência.

## Decisions

**Abas geradas de `GET /catalog/datasources`.** `catalog.area` guarda o id da fonte ou `shared`. Alternativa descartada: abas fixas de Fomento e Simcc no HTML, que exigiriam mudar a página a cada fonte nova.

**Cor por posição na lista de fontes.** A aba e o cabeçalho recebem `--source-color` com os tokens `--chart-1` a `--chart-5`, repetindo em ciclo. O nome sempre acompanha a cor. Alternativa descartada: guardar a cor na fonte, que exigiria migração para um dado só de apresentação.

**Cabeçalho do banco no lugar da barra de ferramentas.** Mostra nome, id, estado do schema, entidades em uso e datas, com "Verificar agora" e "Sincronizar schema". "Fonte ativa", sincronização automática e "Baixar YAML" vão para a subaba Fonte, junto da variável de conexão. Alternativa descartada: manter os interruptores no topo, que é parte do excesso relatado.

**Dois pesos de aviso.** Estados que impedem a Maria de usar algo viram aviso em destaque, reaproveitando `.banner`. Sincronização automática desligada é o padrão das fontes, então vira uma linha discreta. Alternativa descartada: destaque igual para todos, que deixaria um aviso permanente em todo banco.

**"Usar nas respostas" liga visível e consultável juntos.** O PATCH envia os dois campos. Hoje todas as entidades visíveis são consultáveis, e esse é o caso comum. O estado só contexto continua acessível nas opções avançadas. Alternativa descartada: ligar só `visible`, que obrigaria a um segundo clique logo depois.

**Busca alcança as ocultas.** Alternativa descartada: buscar só no que está à vista, porque quem conhece o banco concluiria que a tabela não existe no catálogo.

**Sai o filtro "Ausentes na origem".** Entidades ausentes continuam com selo na lista, e a defasagem já lista o que sumiu. Alternativa descartada: manter o seletor de filtro ao lado de "Mostrar ocultas", com dois controles para quase a mesma escolha.

**Opções da coluna na linha expansível que já existe.** A linha de edição de valores passa a abrir as opções e os valores juntos, reaproveitando `catalog.expanded`. Alternativa descartada: um modal, que afastaria a edição da coluna e pioraria a 375px.

**Disponibilidade entre fontes calculada na página.** A regra é ter um link `active` cujas duas fontes estejam com `enabled`, a partir de `GET /catalog/links` e da lista de fontes. Alternativa descartada: novo campo na API, fora do escopo de apresentação. A fonte sem entidade consultável não entra no cálculo, porque um link `active` já exige colunas utilizáveis.

**Abrir a entidade de uma ponta da ligação.** A API devolve o nome qualificado da entidade; a página carrega a lista do banco, encontra a entidade e a seleciona, com "Mostrar ocultas" ligado quando ela estiver oculta. Alternativa descartada: só citar a coluna no texto, deixando a busca manual.

**Formulário de nova ligação em `<details>`.** Criar ligação é raro. Alternativa descartada: mantê-lo sempre aberto.

**Relacionamentos seguem como estão, na subaba própria.** Já estão fora da visão principal, e a pessoa não pediu para mudá-los. Alternativa descartada: movê-los para as opções avançadas da entidade, o que espalharia uma lista por fonte.

**Tema claro fixo.** Sai o bloco `prefers-color-scheme: dark`, e `color-scheme: light` mantém os controles nativos claros. Os tokens de gráfico ficam menos saturados, e sai a seta de `/docs`. Alternativa descartada: manter o escuro como opção, que preservaria o visual rejeitado pelo usuário.

## Risks / Trade-offs

- [Coluna com acesso `aggregate` esquecida atrás das opções, com efeito em LGPD] → Selo sempre visível com as opções fechadas, e a coluna oculta segue listada em "Mostrar ocultas".
- [Quem conhecia a tela antiga não acha um controle] → README descreve onde cada um foi parar, e a subaba Fonte concentra os controles que saíram do topo.
- [Regra de disponibilidade na página diverge de `chat.py`] → A regra é curta e usa o mesmo `active`; `chat.py` segue como referência, e um desvio afeta só o aviso, nunca a ferramenta.
- [Ligar "Usar nas respostas" expõe tabela ao modelo com um clique] → É o que o interruptor já fazia em dois passos; colunas novas seguem ocultas, e a prévia mostra o resultado.
- [Sem testes automatizados de JavaScript no projeto] → Verificação no navegador nas duas larguras, contra a API real, conforme `tasks.md`.
