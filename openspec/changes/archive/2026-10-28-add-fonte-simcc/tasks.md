# Tasks

## 1. Seed do Simcc

- [x] 1.1 Criar `catalog/simcc.yaml` com a fonte `simcc` (`SIMCC_DATABASE_URL`, schema `public`, descrição) e as entidades da proposta. Listar só as colunas úteis (D2), com acesso `full` em `researcher.name`, `orcid` e `abstract` (D3), as colunas pesquisáveis do requisito "Busca textual no Simcc" e nenhum `values` (D5). Testes em `tests/test_catalog_yaml.py`: o arquivo carrega; nenhuma coluna declara `values`; as pesquisáveis são exatamente as do requisito; `name`, `orcid` e `abstract` são `full`; nenhuma coluna técnica do D2 aparece no arquivo.
- [x] 1.2 Escrever as instruções da fonte `simcc` com dois conteúdos:
  - quando usar tabelas base e quando usar views canônicas, que as views podem estar defasadas e que o ano está em `year_`;
  - a ligação com o fomento pelo Lattes, com o limite de `QUERY_MAX_ROWS` Lattes por consulta, a obrigação de informar quantos foram encontrados e o aviso de que agregações maiores ainda não são possíveis (D4).

  Teste em `tests/test_catalog_context.py`: a prévia gerada a partir do seed contém a orientação das views canônicas, `year_`, a equivalência `lattes_id` ↔ `pesquisadores.lattes` e a orientação de cobertura.
- [x] 1.3 Escrever os exemplos few-shot do Simcc:
  - artigos por ano em `mv_canonical_articles`;
  - artigos de um Lattes com Qualis dado, nas tabelas base;
  - patentes concedidas desde um ano, em `mv_canonical_patents`;
  - projetos sobre um tema com `MATCH_TEXT`, em `mv_canonical_research_projects`;
  - pesquisadores com mais artigos, em `researcher_production` com `researcher`.

  Teste em `tests/test_catalog_yaml.py`, no molde do teste do fomento: todos os exemplos passam nas regras do catálogo semeado. Outro teste usa uma origem SQLite temporária com uma `mv_canonical_articles` que tem `search_vector`, `researcher_ids` e `platform_authors`: depois de seed e sincronização, essas colunas ficam ocultas e fora da prévia.
- [x] 1.4 Documentar a fonte no README: seção do catálogo, `SIMCC_DATABASE_URL` na tabela de configuração e a decisão sobre dados pessoais. Acrescentar `SIMCC_DATABASE_URL` comentada no `.env.example`, apontando para `localhost:5434/simcc` em dev.

## 2. Ligação com o fomento e várias fontes no contexto

- [x] 2.1 Acrescentar às instruções de `catalog/fomento.yaml` que artigos, livros, capítulos, patentes, softwares, eventos e projetos do currículo estão na fonte `simcc`, ligada pelo Lattes. Teste em `tests/test_catalog_context.py`: a prévia do fomento, gerada a partir do seed, indica a fonte `simcc`. Rodar `tests/test_catalog_yaml.py` para garantir que os exemplos do fomento seguem aceitos.
- [x] 2.2 Testes em `tests/test_agent_chat.py` para o requisito "Várias fontes no contexto":
  - com `fomento` e `simcc` ativos e consultáveis, o prompt de sistema contém os dois textos de `render_context`, nessa ordem;
  - com `simcc` desativado, só o do fomento.

  Se algum teste falhar, ajustar `get_consultable_sources_and_contexts`. Pelo D7, não se espera mudança de código.

## 3. Deploy

- [x] 3.1 No `compose.prod.yaml`, colocar a `maria-api` também na rede externa `${SIMCC_NETWORK:-simcc-network}` (D6). Acrescentar `SIMCC_NETWORK` e o exemplo de `SIMCC_DATABASE_URL` com o host `read_db` ao bloco de deploy do `.env.example`. Validar com `docker compose -f compose.prod.yaml config --quiet`.
- [x] 3.2 Atualizar `docs/deploy.md`:
  - o diagrama, com a rede do Simcc;
  - o passo para criar o usuário somente leitura `maria_leitura` no `read_db` do Simcc, com as mesmas permissões e `default_transaction_read_only` do fomento;
  - as variáveis `SIMCC_NETWORK` e `SIMCC_DATABASE_URL`;
  - o seed com `catalog/fomento.yaml catalog/simcc.yaml` e a sincronização das duas fontes;
  - a ordem de inicialização (Simcc e fomento antes da Maria);
  - as linhas de diagnóstico para a fonte `simcc`.

## 4. Verificação com o Simcc real (depois que o ETL terminar de popular o banco de leitura)

- [x] 4.1 Em dev, com `SIMCC_DATABASE_URL` apontando para `localhost:5434/simcc`:
  - rodar `task seed` e `POST /catalog/datasources/simcc/sync`;
  - confirmar que nenhuma coluna do YAML ficou ausente, que as colunas técnicas estão ocultas e que a prévia não tem exemplos recusados;
  - aplicar a instrução nova do fomento por `PATCH /catalog/datasources/fomento`, porque o seed não sobrescreve.
- [x] 4.2 Medir o tempo da sincronização e de `POST /catalog/datasources/simcc/check`, incluindo a leitura de valores observados, e listar as colunas que falharam por timeout. Registrar os números na mudança. Se o custo for alto, decidir com o usuário entre `aggregate` ou ocultar e uma mudança própria (risco do design).
- [x] 4.3 Conferir, só com leituras, quantos Lattes de `pesquisadores.lattes` do fomento existem em `researcher.lattes_id` do Simcc, e se o formato bate (16 dígitos, zeros à esquerda).
- [x] 4.4 Na demo, fazer as perguntas e conferir as respostas:
  - "Quantos artigos únicos por ano desde 2020?": usa a view canônica;
  - os artigos de um pesquisador pelo nome: busca com `MATCH_TEXT` e usa as tabelas base;
  - as produções de um bolsista do fomento: duas etapas pelo Lattes, informando a cobertura;
  - uma agregação sobre todos os bolsistas de doutorado: declara o limite.
- [x] 4.5 Verificar a demo no navegador, no desktop e a 375px: o seletor lista Fomento e Simcc, as entidades do Simcc aparecem com rótulos, os valores lidos da origem aparecem em `type` e `qualis`, e a prévia de contexto não tem exemplos recusados. Desfazer qualquer edição de teste no catálogo.
- [x] 4.6 Rodar `task test` (lint, testes e cobertura) sem falhas.

## Resultados da verificação (2026-10-28)

Banco de leitura do Simcc com 102 pesquisadores: 99 bolsistas reais do fomento (amostra de 100, 25 por modalidade; um currículo não foi encontrado pelo ETL) e os 3 de teste. Os dados somam 1.018 produções bibliográficas, 232 artigos (230 canônicos), 2.362 participações em eventos, 284 projetos, 4 patentes e 3 softwares.

- **4.1:** o seed criou 23 entidades e 157 colunas; a sincronização trouxe 94 entidades e 79 relacionamentos.
  - Todas as entidades e colunas do YAML estão presentes e visíveis.
  - Nenhuma coluna técnica ficou visível, e nenhuma entidade fora do seed ficou visível.
  - A prévia não tem exemplos recusados.
  - A instrução do fomento foi aplicada por `PATCH`.
- **4.2:** a sincronização levou 1,6 s e a verificação 1,5 s, já com a leitura de valores observados, sem nenhuma coluna com timeout.
  - Os valores observados de `type` (5) e `qualis` (10) são categorias reais.
  - Com este volume, ainda entram como valores colunas que serão texto livre com mais dados: `researcher.orcid` (30), os títulos de patentes e softwares, e `jcr` (38).
  - O volume é pequeno para concluir sobre o custo com o Simcc completo: o risco do design segue valendo e deve ser medido na carga real.
- **4.3:** os dois lados usam 16 dígitos com zeros à esquerda preservados.
  - Os 99 Lattes reais do Simcc casam exatamente com `pesquisadores.lattes`, inclusive os 10 que começam com zero.
  - Nenhum pesquisador do Simcc fica sem par no fomento.
  - Os 3 de teste casam com as linhas do fomento alteradas temporariamente.
- **Contexto:** a prévia do Simcc tem 24,4 mil caracteres e a do fomento 12 mil, cerca de 36 mil caracteres no prompt de sistema de cada chamada.
- **4.4:** cada pergunta foi feita numa conversa nova da demo, com o modelo real.
  - Artigos por ano desde 2020: uma tabela que bate com `mv_canonical_articles`. Em 2025 são 29, contra 30 na tabela base, que duplica um artigo com coautor.
  - Artigos de Leonardo Campos Cerqueira: 20 artigos por ano e periódico; o duplicado de 2025 foi listado uma vez.
  - Bolsistas de doutorado da UESC que começaram em 2015: 4 artigos, com a cobertura "2 dos 20 bolsistas" informada, igual à conferência direta nos bancos.
  - Todos os bolsistas de doutorado: a Maria declara que não dá para somar os 3.653 com Lattes, por causa do limite de 100 por consulta.
  - **Achado: consumo de tokens.** As quatro respostas gastaram 50.379, 27.026, 37.710 e 35.707 tokens, contra 8.185 de uma pergunta só com o fomento. Com o teto padrão `CONVERSATION_TOKEN_CEILING=100000`, uma conversa é bloqueada na terceira pergunta.
  - **Detalhe visual:** a tabela da demo mostra o ano como "2.020", com separador de milhar.
- **4.5:** no desktop e a 375px (sem rolagem horizontal):
  - o seletor lista "Fomento à pesquisa" e "Produção científica (Simcc)";
  - as 23 entidades visíveis aparecem com rótulo, e `bibliographic_production.type` mostra "valores (5), 5 a revisar";
  - a prévia não tem exemplos recusados e não mostra colunas técnicas.
  - Os três Lattes do fomento alterados para o teste foram restaurados aos valores originais, e o catálogo não teve edições de teste.
- **4.6:** `task test` passou com 236 testes, lint limpo e 96% de cobertura.

## Workflow follow-up

- Sincronizar as specs e arquivar com `/opsx:archive`.
- Commits no padrão do histórico: `docs(openspec): planeja add-fonte-simcc`, depois `feat: ...` com "Implementa openspec/changes/add-fonte-simcc." e por fim `docs(openspec): arquiva add-fonte-simcc`.
- Em seguida, propor a mudança de consultas entre fontes com DuckDB, que depende desta.
