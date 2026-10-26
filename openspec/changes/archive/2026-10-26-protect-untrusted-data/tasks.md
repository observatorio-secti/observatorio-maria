# Tasks: Proteção contra Prompt Injection e Dados Não Confiáveis

## 1. Sanitização leve, PII e Envelopamento no QueryRunner

- [x] 1.1 Criar módulo `src/observatorio_maria/query/sanitization.py` com funções de escape de delimitadores de quarentena, mascaramento leve de CPF e e-mail (LGPD), e truncamento defensivo a 2.000 caracteres por célula.
- [x] 1.2 Integrar sanitização e envelopamento em tags `<untrusted_database_data>` no retorno de `query_data` em `src/observatorio_maria/query/tool.py`, mantendo `ResultStore` compatível com gráficos e tabelas.
- [x] 1.3 Adicionar testes unitários cobrindo escape de tags, redação de CPFs e e-mails, truncamento de células longas e formato de envelopamento em `tests/test_sanitization.py` e `tests/test_query_execution.py`.

## 2. Reforço defensivo no Prompt de Sistema e Documentação

- [x] 2.1 Atualizar `TOOL_RULES_PROMPT` em `src/observatorio_maria/llm/prompts.py` estabelecendo a regra de quarentena e a ordem de precedência que instrui a Maria a ignorar comandos embutidos em dados não confiáveis.
- [x] 2.2 Atualizar a documentação de segurança e privacidade no `README.md` descrevendo a proteção contra prompt injection indireto e mascaramento de PII.
- [x] 2.3 Adicionar testes de integração simulando tentativas de injeção indireta em dados de retorno em `tests/test_agent_chat.py`.

## 3. Verificação e conformidade

- [x] 3.1 Executar verificação completa com `task lint` e `task test`, garantindo que todos os testes passem e a cobertura permaneça acima de 90%.
