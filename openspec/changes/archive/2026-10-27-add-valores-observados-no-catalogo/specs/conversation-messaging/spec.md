## MODIFIED Requirements

### Requirement: Orçamento de chamadas por resposta
Cada resposta SHALL usar no máximo `MARIA_AGENT_MAX_MODEL_CALLS` chamadas ao modelo (padrão 6, mínimo 1), contando a que produz a resposta final. Valores menores que 1 MUST impedir a inicialização da aplicação.

#### Scenario: Orçamento respeitado
- **WHEN** o modelo pede uma nova consulta em todas as chamadas
- **THEN** a resposta é concluída com exatamente 6 chamadas ao modelo

#### Scenario: Orçamento configurado
- **WHEN** `MARIA_AGENT_MAX_MODEL_CALLS` é 3 e o modelo pede uma nova consulta em todas as chamadas
- **THEN** a resposta é concluída com exatamente 3 chamadas ao modelo

## ADDED Requirements

### Requirement: Ausência de dados só depois de conferir
As instruções do modelo SHALL dizer que, diante de um resultado vazio ou nulo numa consulta filtrada por texto, ele deve conferir os valores existentes antes de afirmar ao usuário que não há dados, enquanto houver chamadas no orçamento.

#### Scenario: Regra no prompt
- **WHEN** a Maria monta o prompt de sistema com fontes ativas
- **THEN** o prompt contém a regra de conferir os valores existentes antes de concluir que não há dados

#### Scenario: Correção do filtro
- **WHEN** a primeira consulta filtra `modalidade = 'Doutorado'`, volta nula com aviso e o modelo consulta os valores distintos
- **THEN** a chamada seguinte ainda pode consultar com `modalidade = 'Doutorado - Cotas'` e a resposta usa esse resultado
