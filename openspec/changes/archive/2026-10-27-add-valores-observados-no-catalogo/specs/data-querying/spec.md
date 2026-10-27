## ADDED Requirements

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
