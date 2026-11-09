# Spec Delta

## Purpose

Ranqueia pesquisadores do Simcc por relevância textual a um tema, com o mesmo critério da busca V2 do Simcc, e explica a posição de cada um com evidências e a data dos dados.

## ADDED Requirements

### Requirement: Ranking por relevância
A ferramenta `search_researchers` SHALL devolver os pesquisadores do Simcc cujo resumo do currículo ou alguma produção casa com o termo, ordenados por relevância decrescente: relevância do resumo × 1,5, mais a maior relevância entre as produções, mais ln(nº de produções que casam + 1). Empates MUST ser desfeitos por nome e depois pelo identificador.

#### Scenario: Especialistas por produção
- **WHEN** o modelo chama `search_researchers` com o termo "dengue"
- **THEN** pesquisadores com muitas produções sobre dengue aparecem antes de quem só cita o termo uma vez no resumo

#### Scenario: Ordem estável
- **WHEN** a mesma busca é feita duas vezes sem refresh das views entre elas
- **THEN** a ordem dos pesquisadores é a mesma

### Requirement: Mesma base da busca do Simcc
O ranking SHALL usar o índice de busca mantido pelo Simcc (as views `mv_search_documents` e `mv_researcher_search`), com a sintaxe de busca web em português sem acentos: radicais, `"frase exata"`, `OR` e `-exclusão`. A Maria MUST apenas ler essas views, sem criá-las, alterá-las ou atualizá-las.

#### Scenario: Acento e radical
- **WHEN** o termo é "educacao"
- **THEN** produções com "Educação" e "educacional" contam como evidência

#### Scenario: Somente leitura
- **WHEN** a ferramenta é executada
- **THEN** nenhuma instrução além de SELECT é enviada ao banco do Simcc

### Requirement: Filtros do ranking
A ferramenta SHALL aceitar, opcionalmente, ano inicial e final, tipos de produção (artigo, livro, capítulo, patente, software, evento, área de atuação) e uma instituição por sigla ou nome. Período e tipos MUST restringir as produções que contam; com tipos informados, o resumo do currículo MUST deixar de contar. A instituição MUST restringir os pesquisadores.

#### Scenario: Período
- **WHEN** o modelo busca "dengue" de 2020 a 2025
- **THEN** só produções desse intervalo contam para a posição e para as evidências

#### Scenario: Só patentes
- **WHEN** o modelo busca "vacina" com o tipo patente
- **THEN** só pesquisadores com patentes que casam com o termo aparecem, e o resumo não conta

#### Scenario: Instituição
- **WHEN** o modelo busca "inteligência artificial" na instituição "UFBA"
- **THEN** só pesquisadores com vínculo na UFBA aparecem

#### Scenario: Unidades da instituição
- **WHEN** o modelo informa a sigla "UFBA"
- **THEN** pesquisadores vinculados a unidades com "UFBA" no nome, como uma escola da universidade, também aparecem

#### Scenario: Instituição ambígua
- **WHEN** o texto informado não é sigla nem nome exato e casa com mais de 20 instituições, como "Bahia"
- **THEN** a ferramenta devolve um erro pedindo a sigla ou o nome completo

#### Scenario: Instituição desconhecida
- **WHEN** nenhuma instituição corresponde à sigla ou ao nome informado
- **THEN** a ferramenta devolve um erro explicado ao modelo, sem consultar o ranking

### Requirement: Evidências por pesquisador
Cada pesquisador do ranking SHALL trazer o total de produções que casam com o termo, a contagem por tipo e até 3 evidências (tipo, título e ano), escolhidas pela maior relevância. Quando o resumo do currículo casa com o termo, ele MUST poder aparecer como evidência do tipo perfil, sem o texto do resumo.

#### Scenario: Evidências de produção
- **WHEN** um pesquisador tem 38 produções sobre dengue
- **THEN** o card informa 38 produções e mostra as 3 mais relevantes com título, tipo e ano

#### Scenario: Só o perfil casa
- **WHEN** o pesquisador entra no ranking só pelo resumo do currículo
- **THEN** o total de produções é zero e a evidência mostrada é o perfil

### Requirement: Tamanho do ranking
A ferramenta SHALL devolver até 10 pesquisadores por padrão e no máximo 20, e MUST informar quantos pesquisadores casam com o termo no total.

#### Scenario: Pedido acima do máximo
- **WHEN** o modelo pede 50 pesquisadores
- **THEN** a ferramenta devolve no máximo 20 e o total de pesquisadores encontrados

### Requirement: Data dos dados do ranking
A ferramenta SHALL informar a data do último refresh do índice de busca, lida dos metadados do Simcc. Sem metadados, a data MUST ficar ausente, sem impedir o ranking.

#### Scenario: Data conhecida
- **WHEN** o índice foi atualizado em 08/11/2026
- **THEN** o resultado informa essa data

### Requirement: Índice de busca indisponível
Quando as views do índice de busca não existem ou estão vazias, a ferramenta SHALL devolver ao modelo um erro dizendo que a busca por relevância está indisponível, sem bloco e sem lista vazia apresentada como ausência de pesquisadores.

#### Scenario: Views vazias
- **WHEN** `mv_search_documents` não tem linhas
- **THEN** o modelo recebe o erro e nenhum bloco de pesquisadores é criado

### Requirement: Termo e fonte válidos
A ferramenta SHALL recusar termo vazio e SHALL exigir a fonte `simcc` ativa em PostgreSQL, devolvendo erro explicado ao modelo nos demais casos. Mensagens de erro MUST NOT repetir URLs de conexão.

#### Scenario: Termo vazio
- **WHEN** o modelo chama a ferramenta com termo em branco
- **THEN** recebe um erro pedindo o termo da busca

#### Scenario: Fonte inativa
- **WHEN** a fonte `simcc` está desativada
- **THEN** recebe um erro dizendo que o ranking está indisponível

### Requirement: Dados do ranking como dados não confiáveis
Nomes e títulos devolvidos ao modelo pela ferramenta SHALL passar pela mesma sanitização, mascaramento de dados pessoais e envelopamento `<untrusted_database_data>` das consultas comuns, e o resultado MUST ganhar um `result_id` reutilizável pelas ferramentas de apresentação.

#### Scenario: Título com instrução
- **WHEN** um título de produção contém "ignore as instruções anteriores"
- **THEN** o texto chega ao modelo dentro do envelope de dados não confiáveis

### Requirement: Consulta contada no orçamento
Cada chamada a `search_researchers` SHALL contar como uma consulta no limite de consultas por chamada, aparecer como atividade de consulta ao Simcc e respeitar o limite de tempo das consultas.

#### Scenario: Atividade
- **WHEN** o modelo chama `search_researchers` com o propósito "Buscando especialistas em dengue"
- **THEN** a página recebe a atividade de consulta ao Simcc com esse propósito
