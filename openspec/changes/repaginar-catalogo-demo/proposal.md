# Proposal

## Why

A aba "Catálogo de dados" da demo é onde se configura a Maria, e ficou difícil de usar: um seletor discreto é a única indicação do banco em edição, e cada uma das 1032 colunas locais traz dois interruptores e dois seletores, embora só 1 coluna use `aggregate`, 27 sejam pesquisáveis e 20 tenham listagem manual. Quem configura conhece os bancos, mas perde tempo com opções que raramente mudam e não vê com clareza o que está desligado nem como ligar.

## What Changes

- Abas por banco no lugar do seletor, uma para cada fonte cadastrada, com cor e nome fixos no cabeçalho. Uma aba **Entre fontes** reúne o que não pertence a um banco: conceitos, ligações e consultas entre fontes.
- A lista de entidades mostra por padrão só as usadas pela Maria, com "Mostrar ocultas". A busca alcança também as ocultas. O interruptor por linha sai da lista.
- A entidade fica com **Usar nas respostas**, rótulo e descrição à vista. Consultável, sinônimos e conceito vão para "Opções avançadas".
- As colunas mostram nome, tipo, visível e descrição, só das visíveis por padrão. Acesso, pesquisável, valores no contexto e descrição dos valores vão para "Opções" de cada coluna, e o que foge do padrão aparece como selo mesmo com as opções fechadas.
- Ativar a fonte, sincronização automática e baixar YAML vão para a subaba da fonte, e o cabeçalho do banco mostra o estado.
- Avisos com ação direta para o que está desligado: fonte inativa, sincronização automática, entidade oculta, entidade não consultável, ligação sem efeito e consultas entre fontes indisponíveis.

- A página inteira passa a usar só um tema claro, com cores sóbrias e sem emojis ou símbolos decorativos, por pedido do usuário. Isso alcança também Chat e Contrato de blocos.

### Fora do escopo

- Qualquer mudança de API, esquema, migração ou comportamento do agente: todas as capacidades da aba continuam disponíveis.
- Unir visível e consultável num controle só.
- Reorganizar as abas Chat e Contrato de blocos: elas só herdam o tema.
- Avisos sobre funções ligadas por variável de ambiente.
- Editar os exemplos few-shot, que seguem fora da demo.

## Capabilities

### New Capabilities

Nenhuma.

### Modified Capabilities

- `demo-page`: navegação por banco, aba Entre fontes, listas focadas no que está em uso, opções avançadas e avisos com ação na aba "Catálogo de dados".

## Impact

- Código: `src/observatorio_maria/demo/index.html`, `catalog.js` e `styles.css`, que perde o bloco de tema escuro.
- Documentação: seção Demo e fluxo de nova fonte do `README.md`.
- Sem alteração em bancos externos, segredos ou endpoints. A aba usa os mesmos endpoints do catálogo, ainda sem autenticação.
- Não depende de mudanças não arquivadas. `add-visao-territorial` também tem delta de `demo-page`, mas sobre outros requisitos.
