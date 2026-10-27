# data-querying Specification

## Purpose
Define como a Maria consulta os dados das fontes do catálogo para responder perguntas: o que pode ser consultado, as garantias de somente leitura e privacidade, a busca textual e os resultados que alimentam gráficos e tabelas.

## Requirements

### Requirement: Consulta apenas a fontes do catálogo
O modelo SHALL poder consultar apenas fontes ativas do catálogo que tenham ao menos uma entidade visível, consultável e presente, identificando a fonte pelo seu `id`. Cada consulta MUST se referir a uma única fonte. Consulta a fonte inexistente, desativada ou sem entidades consultáveis MUST ser recusada.

#### Scenario: Fonte ativa consultada
- **WHEN** o modelo consulta a fonte `fomento`, ativa e com entidades consultáveis
- **THEN** a consulta é validada e executada nessa fonte

#### Scenario: Fonte desativada
- **WHEN** o modelo consulta uma fonte desativada
- **THEN** a consulta é recusada sem acessar a origem

### Requirement: Somente leitura
A consulta MUST ser uma única instrução `SELECT`, opcionalmente com `WITH`. Qualquer outra instrução (inserção, alteração, remoção, DDL, permissões, mais de uma instrução) MUST ser recusada antes de chegar à origem. A execução SHALL ocorrer numa transação somente leitura e MUST NOT alterar objetos ou dados da origem.

#### Scenario: Alteração recusada
- **WHEN** o modelo envia `UPDATE bolsas SET status = 'REGULAR'`
- **THEN** a consulta é recusada e nada é enviado à origem

#### Scenario: Instruções encadeadas
- **WHEN** o modelo envia `SELECT 1; DELETE FROM bolsas`
- **THEN** a consulta inteira é recusada

### Requirement: Entidades permitidas
A consulta SHALL referenciar apenas entidades visíveis, consultáveis e presentes no catálogo da fonte. Entidade oculta, ausente ou inexistente MUST ser recusada com a mesma mensagem, sem revelar se ela existe na origem. Entidade visível mas não consultável MUST ser recusada como somente referência.

#### Scenario: Entidade oculta
- **WHEN** o modelo consulta uma tabela de ingestão oculta no catálogo
- **THEN** a consulta é recusada com a mesma mensagem dada a uma tabela inexistente

#### Scenario: Entidade só de referência
- **WHEN** o modelo consulta uma entidade visível e não consultável
- **THEN** a consulta é recusada informando que a entidade é somente de referência

### Requirement: Colunas permitidas
A consulta SHALL referenciar apenas colunas visíveis e presentes das entidades permitidas. Coluna oculta, ausente ou inexistente MUST ser recusada com a mesma mensagem. `SELECT *` e `entidade.*` MUST ser recusados, para que colunas ocultas nunca sejam lidas.

#### Scenario: Coluna oculta
- **WHEN** o modelo seleciona uma coluna oculta de `bolsas`
- **THEN** a consulta é recusada com a mesma mensagem dada a uma coluna inexistente

#### Scenario: Asterisco
- **WHEN** o modelo envia `SELECT * FROM projetos`
- **THEN** a consulta é recusada pedindo que as colunas sejam listadas

### Requirement: Colunas somente para agregação
Uma coluna com acesso `aggregate` SHALL poder aparecer em filtros, junções, agrupamentos e dentro de funções de agregação, e MUST NOT aparecer, direta ou indiretamente, entre as colunas devolvidas pela consulta.

#### Scenario: Contagem permitida
- **WHEN** o modelo conta bolsas filtrando por `cep_referencia LIKE '40%'`
- **THEN** a consulta é executada

#### Scenario: Valor individual recusado
- **WHEN** o modelo seleciona `cep_referencia`, mesmo com `GROUP BY cep_referencia` ou dentro de outra expressão que não seja agregação
- **THEN** a consulta é recusada informando que a coluna é somente para agregação

### Requirement: Funções permitidas
A consulta SHALL usar apenas funções de uma lista permitida (agregações, datas, texto, conversões e condicionais comuns, além de `MATCH_TEXT`). Conectores lógicos como `AND`, `OR` e `XOR`, bem como predicados `EXISTS`, SHALL ser permitidos em expressões booleanas e MUST NOT ser tratados como funções proibidas. Qualquer função fora da lista permitida MUST ser recusada, informando as funções disponíveis.

#### Scenario: Operadores lógicos compostos
- **WHEN** o modelo envia consulta com `WHERE status = 'REGULAR' AND modalidade = 'DCR'`
- **THEN** a consulta é aceita sem erro de função proibida

#### Scenario: Predicado EXISTS em subconsulta
- **WHEN** o modelo envia consulta com `WHERE EXISTS (SELECT 1 FROM public.projetos_palavras_chave WHERE projeto_id = p.id)`
- **THEN** a consulta é aceita sem erro de função proibida

#### Scenario: Função de sistema
- **WHEN** o modelo usa `pg_sleep(10)` ou `pg_read_file('...')`
- **THEN** a consulta é recusada antes de chegar à origem

### Requirement: Limite de linhas
Toda consulta SHALL devolver no máximo `QUERY_MAX_ROWS` linhas (padrão 100). Caso a consulta contenha cláusula `LIMIT`, o valor MUST ser inteiro positivo e MUST NOT exceder `QUERY_MAX_ROWS`; caso exceda, a consulta MUST ser recusada antes da execução. Se omitido, o limite máximo continua aplicado pelo executor, e o resultado MUST informar se foi truncado.

#### Scenario: Limite excessivo recusado
- **WHEN** o modelo envia consulta com `LIMIT 500` e `QUERY_MAX_ROWS` é 100
- **THEN** a consulta é recusada informando que o limite solicitado excede o máximo permitido

#### Scenario: Limite aceito
- **WHEN** o modelo envia consulta com `LIMIT 10`
- **THEN** a consulta é aceita e executada

#### Scenario: Resultado truncado
- **WHEN** a consulta produziria 500 linhas sem cláusula `LIMIT` e `QUERY_MAX_ROWS` é 100
- **THEN** o resultado tem 100 linhas e indica que foi truncado

### Requirement: Limite de tempo
Toda consulta SHALL ser interrompida após `QUERY_TIMEOUT_SECONDS` (padrão 15). Em bancos PostgreSQL, a execução MUST definir `statement_timeout` correspondente na sessão da transação para cancelamento no servidor. A interrupção por timeout de cliente ou cancelamento de statement no banco MUST virar uma recusa por tempo esgotado e MUST NOT derrubar a resposta.

#### Scenario: Consulta lenta interrompida no cliente
- **WHEN** a consulta passa do limite de tempo no cliente
- **THEN** ela é cancelada e o modelo recebe que o tempo se esgotou

#### Scenario: Consulta cancelada por statement_timeout
- **WHEN** o servidor PostgreSQL interrompe a consulta por statement_timeout
- **THEN** ela é tratada como recusa por tempo esgotado sem expor dados de conexão

### Requirement: Recusas e erros explicados ao modelo
Recusa de validação, erro da origem (sintaxe, tipo) e origem inacessível SHALL voltar ao modelo como resultado da consulta, com um motivo curto que permita corrigi-la, e MUST NOT encerrar a resposta com erro. O motivo MUST NOT conter URLs de conexão nem credenciais.

#### Scenario: Erro de sintaxe corrigido
- **WHEN** a primeira consulta tem erro de sintaxe e ainda há chamadas no orçamento
- **THEN** o modelo recebe o erro e pode enviar a consulta corrigida na chamada seguinte

#### Scenario: Origem inacessível
- **WHEN** `FOMENTO_DATABASE_URL` aponta para um banco fora do ar
- **THEN** o modelo recebe que a fonte está indisponível, sem a URL, e a resposta ao usuário diz que não foi possível consultar os dados

### Requirement: Busca textual
A consulta SHALL aceitar `MATCH_TEXT(coluna, 'termo', ...)`, verdadeira quando a coluna contém ao menos um dos termos, sem diferenciar maiúsculas, minúsculas e acentos. O prompt de regras da Maria MUST orientar o modelo a chamar `MATCH_TEXT` como função com a assinatura `MATCH_TEXT(coluna, 'termo1', 'termo2')`, sem operadores infixos ou operadores de similaridade não padrão. Termos vazios MUST ser recusados.

#### Scenario: Tema com sinônimos
- **WHEN** o modelo filtra projetos por `MATCH_TEXT(resumo, 'dengue', 'aedes aegypti', 'arbovirose')`
- **THEN** voltam os projetos cujo resumo contém qualquer um dos termos, inclusive "Dengue" e "ARBOVIROSES"

#### Scenario: Acentos ignorados
- **WHEN** o modelo busca `MATCH_TEXT(nome, 'saude')`
- **THEN** projetos com "Saúde" no título são encontrados

### Requirement: Busca apenas em colunas pesquisáveis
`MATCH_TEXT` SHALL ser aceita apenas em colunas marcadas como pesquisáveis no catálogo. Em outra coluna, a consulta MUST ser recusada, informando as colunas pesquisáveis da entidade.

#### Scenario: Coluna não pesquisável
- **WHEN** o modelo usa `MATCH_TEXT(nome_curso, 'medicina')` e `nome_curso` não é pesquisável
- **THEN** a consulta é recusada listando as colunas pesquisáveis de `bolsas`

### Requirement: Consultas por chamada
Numa mesma chamada, o modelo SHALL poder pedir várias consultas, executadas de forma independente, até `QUERY_MAX_PER_CALL` (padrão 4). As que passarem do limite MUST ser recusadas sem execução.

#### Scenario: Consultas paralelas
- **WHEN** o modelo pede, na mesma chamada, a contagem por modalidade e a lista de projetos
- **THEN** as duas são executadas e os dois resultados voltam ao modelo

#### Scenario: Excesso de consultas
- **WHEN** o modelo pede 6 consultas numa chamada e o limite é 4
- **THEN** as 4 primeiras são executadas e as 2 últimas são recusadas por excesso

### Requirement: Resultados identificados
Cada consulta executada SHALL produzir um resultado com identificador próprio, colunas (nome e tipo), linhas e a indicação de truncamento. O resultado SHALL valer apenas dentro da resposta em que foi gerado e MUST NOT ser persistido no banco da Maria.

#### Scenario: Resultado referenciável
- **WHEN** uma consulta é executada com sucesso
- **THEN** o modelo recebe um identificador do resultado que pode usar para pedir um gráfico ou tabela na mesma resposta

### Requirement: Envelopamento e sanitização de dados não confiáveis
Todo resultado de consulta retornado à IA SHALL ser envelopado em tags semânticas `<untrusted_database_data>` identificando a fonte. O sistema MUST escapar tags de fechamento presentes nos dados do banco (convertendo em entidades seguras) e MUST truncar textos de células individuais em no máximo 2.000 caracteres indicando truncamento.

#### Scenario: Envelopamento com delimitadores seguros
- **WHEN** a consulta retorna linhas de projetos com resumo textual
- **THEN** a resposta da ferramenta contém os dados encapsulados em `<untrusted_database_data>` e registros estruturados

#### Scenario: Escape de tentativa de quebra de delimitador
- **WHEN** o campo de texto do banco contém `</untrusted_database_data>`
- **THEN** a tag é escapada como `&lt;/untrusted_database_data&gt;` impedindo a fuga do bloco

#### Scenario: Truncamento de célula longa
- **WHEN** uma célula de texto do banco possui 5.000 caracteres
- **THEN** o texto é truncado em 2.000 caracteres com sufixo indicando truncamento

### Requirement: Mascaramento preventivo de dados pessoais
O sistema SHALL aplicar filtro leve de privacidade sobre valores textuais retornados em consultas antes do envio à IA, substituindo padrões identificáveis de CPF por `[CPF MASCARADO]` e endereços de e-mail por `[E-MAIL MASCARADO]`, sem alterar os dados no banco de origem.

#### Scenario: CPF mascarado no resumo
- **WHEN** o resumo de um projeto contém `pesquisador CPF 123.456.789-00`
- **THEN** o valor entregue à IA substitui o número por `[CPF MASCARADO]`

#### Scenario: E-mail mascarado no texto
- **WHEN** o texto retornado contém `contato: fulano@provedor.com.br`
- **THEN** o valor entregue à IA substitui o endereço por `[E-MAIL MASCARADO]`

### Requirement: Dry-run de custo estimado com EXPLAIN
Em bancos de dados PostgreSQL, o sistema SHALL executar um dry-run via `EXPLAIN (FORMAT JSON)` antes da execução da consulta e inspecionar o custo total estimado (`Total Cost`). Quando o custo ultrapassar `QUERY_MAX_ESTIMATED_COST` (e o limite for maior que zero), a consulta MUST ser recusada antes de ser executada na origem, devolvendo ao modelo uma explicação com os custos e orientação para restringir a busca.

#### Scenario: Custo estimado dentro do limite aceito
- **WHEN** o modelo envia consulta com custo estimado de 1.200 em relação a um teto de 50.000
- **THEN** a consulta é validada pelo dry-run e executada normalmente

#### Scenario: Custo estimado excessivo recusado
- **WHEN** o modelo envia consulta sem filtros cujo custo estimado pelo PostgreSQL atinge 85.000 (acima do teto de 50.000)
- **THEN** a execução é interrompida antes de tocar nas tabelas e o modelo recebe mensagem explicando que o custo foi excedido com sugestão de filtros

#### Scenario: Verificação desativada com teto zero
- **WHEN** `QUERY_MAX_ESTIMATED_COST` é configurado como 0
- **THEN** a consulta é executada sem bloqueio por custo de dry-run

#### Scenario: Compatibilidade com dialeto SQLite
- **WHEN** a consulta é executada contra uma fonte SQLite
- **THEN** o sistema executa o dry-run compatível ou prossegue para execução sem exigir o formato numérico do PostgreSQL

### Requirement: Aviso de resultado vazio
Quando uma consulta aceita retornar zero linhas, ou uma única linha com todos os valores nulos, o resultado SHALL trazer um aviso ao modelo. O aviso orienta a conferir os valores existentes das colunas filtradas antes de concluir que não há dados. Resultados com dados MUST NOT trazer o aviso.

#### Scenario: Soma nula por filtro errado
- **WHEN** o modelo consulta `SELECT SUM(quantidade) FROM public.mv_bolsas_metricas WHERE modalidade = 'Doutorado'` e o resultado é uma linha com `NULL`
- **THEN** o resultado traz o aviso, além do `result_id` e da linha retornada

#### Scenario: Nenhuma linha
- **WHEN** a consulta aceita retorna zero linhas
- **THEN** o resultado traz o aviso

#### Scenario: Resultado com dados
- **WHEN** a consulta retorna `4158`
- **THEN** o resultado não traz o aviso
