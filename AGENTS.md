# AGENTS.md — Observatório Maria (`observatorio-maria`)

Este repositório faz parte do **Ecossistema Observatório CT&I Bahia**. Ele é versionado de forma independente e implementa a API da **Maria**, o agente conversacional de IA do Observatório, com suporte a streaming SSE, blocos estruturados (`text`, `chart`, `table`), catálogo semântico de dados e observabilidade OpenTelemetry/OpenInference.

> As diretrizes detalhadas do fluxo orientado a especificações também estão em [`openspec/config.yaml`](openspec/config.yaml). Se estiver trabalhando no workspace completo (`Observatorio/`), consulte `../AGENTS.md`.

---

## 1. Princípios Arquiteturais e Regras Inegociáveis

1. **Bancos Externos são Estritamente Somente Leitura (`Read-Only`)**:
   - A Maria consulta bancos externos (como `fomento` na porta `5432` e `simcc` `read_db` na porta `5434`).
   - **Jamais** crie, altere ou remova tabelas, views, roles, comentários ou dados nos bancos de origem — nem mesmo em testes. Defasagem (*schema drift*) e consultas são testadas contra um banco SQLite temporário.
2. **Separação entre Dados Técnicos e Editoriais no Catálogo**:
   - Arquivos `catalog/*.yaml` (`fomento.yaml`, `simcc.yaml`) são **seeds**, nunca fonte de verdade absoluta: `task seed` cria apenas o que falta sem sobrescrever edições manuais feitas via API/demo.
   - A sincronização de schema (`sync`) só atualiza metadados técnicos (tipo, chaves, presença) e nunca sobrescreve rótulos, descrições ou flags de visibilidade/acesso definidos por pessoas. Entidades/colunas novas entram **ocultas** por padrão.
3. **Segurança, LGPD e Limites de Consulta**:
   - Credenciais e URLs de banco nunca são salvas no banco da Maria nem expostas na API ou em mensagens de erro (guarda-se apenas o nome da variável de ambiente, ex.: `FOMENTO_DATABASE_URL`, `SIMCC_DATABASE_URL`).
   - Dados vindos de consultas SQL externas são envelopados em `<untrusted_database_data>` (quarentena contra *prompt injection*) e passam por mascaramento preventivo de PII (CPF e e-mail).
   - Níveis de modelo (`fast`, `medium`, `advanced`) são internos (`ModelRegistry` via `BaseChatModel` do LangChain); o cliente nunca escolhe nem vê o modelo.
4. **Idioma e Convenções**:
   - Artefatos OpenSpec, comentários, mensagens da API, textos da demo, documentação e commits em **Português do Brasil (pt-BR)**.
   - Identificadores de código em **inglês**.

---

## 2. Comandos Padrão de Desenvolvimento

- **Instalar dependências**: `poetry install`
- **Aplicar migrações do banco da Maria**: `poetry run alembic upgrade head`
- **Carregar seeds do catálogo**: `poetry run task seed` (ou `poetry run task seed -- --reset`)
- **Servidor de desenvolvimento**: `poetry run task run`
- **Suíte de testes + lint + cobertura**: `poetry run task test` (nunca chama LLMs reais; usa fakes do LangChain)
- **Lint e formatação**: `poetry run task lint` e `poetry run task format`

---

## 3. Padrão de Documentação e Gatilhos Obrigatórios (Definition of Done)

A documentação deste repositório é mantida em:
- [`README.md`](README.md): Documentação completa da arquitetura, estrutura de diretórios, variáveis `.env`, contrato de blocos SSE, catálogo de dados, segurança, observabilidade e testes.
- [`docs/deploy.md`](docs/deploy.md): Guia de operação e deploy em produção (`compose.prod.yaml`) conectado às redes do Fomento e do SimCC.
- [`openspec/`](openspec/config.yaml): Especificações vivas em `openspec/specs/` e histórico de mudanças em `openspec/changes/`.

### Tabela de Atualização Obrigatória

**Nenhuma tarefa está concluída sem atualizar a documentação correspondente no mesmo ciclo:**

| Se você alterar... | Atualize obrigatoriamente: |
| :--- | :--- |
| Variáveis em `src/observatorio_maria/settings.py` | `.env.example` e a tabela **⚙️ Configuração** no `README.md` |
| Rotas, payloads ou eventos SSE em `routers/` ou `schemas.py` | Seções **🌐 API** / **🗂️ Catálogo de dados** no `README.md` e a página `/demo` (quando voltado ao usuário) |
| Fontes de dados em `catalog/*.yaml` ou regras de deploy/redes Docker | Seção **🗂️ Catálogo de dados** no `README.md` e `docs/deploy.md` |
| Estrutura de arquivos em `src/observatorio_maria/` | Árvore **Estrutura de diretórios** no `README.md` |
| Qualquer funcionalidade via OpenSpec | `openspec/specs/` e `README.md` conforme regras em `openspec/config.yaml` |
