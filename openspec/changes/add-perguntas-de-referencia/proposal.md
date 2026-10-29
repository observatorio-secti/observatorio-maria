# Proposal

## Why

Os testes da Maria usam modelos falsos de propósito, então nada mede se o modelo real escolhe a fonte, a tabela e o filtro certos. As próximas mudanças mexem justamente no contexto enviado ao modelo: conceitos repetidos entre fontes (#2), envio só das fontes relevantes (#3) e consultas entre fontes (#4). Sem uma linha de base, qualquer uma delas pode piorar a precisão sem ninguém perceber. Esta mudança resolve a issue #1 e vem antes das outras.

## What Changes

- **Perguntas de referência versionadas:** um arquivo YAML no repositório com as perguntas, a fonte esperada, o critério de acerto e as consultas de conferência que produziram a resposta esperada.
- **Critérios de acerto:**
  - determinísticos sempre que possível: número na resposta, itens de uma lista, fonte consultada;
  - avaliados por um modelo-juiz só nos critérios textuais, como "declara o limite" e "menciona a outra fonte".
- **Comando `task eval`:** roda as perguntas com o modelo real configurado, fora do `task test`. Mostra um relatório com acerto, tokens, chamadas ao modelo e consultas por pergunta, e grava o resultado em JSON para comparar execuções.
- **Conferência das respostas esperadas:** `task eval -- --check-expected` executa as consultas de conferência nos bancos de origem e aponta as respostas esperadas que ficaram desatualizadas, sem chamar o modelo.
- **Conjunto inicial de 22 perguntas em 8 categorias:** agregações do fomento, totais do Simcc, perguntas sobre um pesquisador, busca textual, consultas entre fontes, conceitos ambíguos, dado ausente e LGPD. Inclui:
  - as quatro perguntas conferidas à mão na verificação da `add-fonte-simcc` (issue #1);
  - perguntas ambíguas entre fontes da issue #2, como "Quantos projetos sobre dengue existem?". A resposta esperada segue a política decidida (fonte padrão + menção da outra), que ainda não está implementada: elas devem falhar hoje e servir de linha de base para a #2;
  - a tag `exemplo` nas perguntas que repetem um exemplo few-shot do catálogo, para separar cópia de exemplo de raciocínio.
- **Documentação:** seção nova no README sobre a avaliação com modelo real.

### Fora do escopo

- Rodar a avaliação na CI: ela chama um LLM real, tem custo e depende dos bancos de dev.
- Implementar a política de conceitos repetidos (#2) ou a redução de contexto (#3).
- Avaliar a apresentação (gráficos e tabelas) além da presença dos números e itens esperados.
- Interface na demo: a avaliação é uma ferramenta de desenvolvimento, não uma funcionalidade voltada ao usuário.

## Capabilities

### New Capabilities

- `answer-evaluation`: avaliação das respostas da Maria com o modelo real contra perguntas de referência versionadas, com critérios de acerto, relatório e conferência das respostas esperadas.

### Modified Capabilities

Nenhuma.

## Impact

- **Código:**
  - novo pacote `src/observatorio_maria/evaluation/` (carregamento das perguntas, execução, critérios, juiz, relatório e CLI);
  - `services/chat.py` ganha um ponto de observação opcional das consultas executadas (fonte, SQL e resultado), usado pela avaliação; sem efeito no comportamento da API;
  - `pyproject.toml` ganha a tarefa `eval`.
- **Arquivos novos:** `evals/reference.yaml` (versionado) e `evals/results/` (ignorado pelo git).
- **Testes:** testes da avaliação com modelos falsos e origem SQLite temporária, dentro do `task test`.
- **Banco da Maria:** nenhuma migração. A avaliação roda numa cópia temporária do banco SQLite, para não deixar conversas de avaliação no banco de dev.
- **Bancos externos:** somente leitura, pelos mesmos caminhos de hoje: as consultas do agente e as consultas de conferência passam pelo validador e pela conexão somente leitura.
- **Segredos:** usa as credenciais já configuradas (`OPENAI_API_KEY`, `FOMENTO_DATABASE_URL`, `SIMCC_DATABASE_URL`); o relatório nunca grava URLs de conexão.
- **Endpoints sem autenticação:** nenhum. Não há endpoint novo.
- **Custo:** cada execução chama o modelo real, cerca de 30 a 50 mil tokens por pergunta com as duas fontes, mais o juiz.
- **Dependências:** não depende de mudança em andamento. É pré-requisito para as propostas das issues #2, #3 e #4.
