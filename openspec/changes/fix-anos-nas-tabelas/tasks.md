# Tasks

## 1. Tipo das colunas de ano

- [ ] 1.1 Escrever os testes dos cenários de "Colunas de ano nas tabelas" (tabela nova, streaming, bloco gravado, `valor_por_ano`, `anos_de_vigencia`, `plano`, valor nulo) e confirmar que falham
- [ ] 1.2 Criar em `schemas.py` a função que decide o tipo e aplicá-la em `TableBlock` por `model_validator`; verificar com os testes de bloco gravado
- [ ] 1.3 Aplicar a função em `show_table` (`query/tool.py`); verificar com os testes de tabela nova e streaming
- [ ] 1.4 Registrar a regra na seção do contrato de blocos do `README.md` e conferir o texto contra a spec

## 2. Verificação

- [ ] 2.1 Rodar `poetry run task test` sem falhas
- [ ] 2.2 Na demo, perguntar "Quantos artigos únicos foram publicados por ano desde 2020?" contra o banco real e confirmar anos sem separador no streaming e ao reabrir a conversa, em desktop e a 375px

## Workflow follow-up

- Arquivar depois da implementação, com commits no padrão do histórico.
- Fechar a issue #6.
