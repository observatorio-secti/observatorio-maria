# Spec Delta

## ADDED Requirements

### Requirement: Resposta montada por ordem de chegada
Durante o streaming, a página SHALL mostrar textos e blocos na ordem em que chegam, sem redesenhar os gráficos já exibidos. Ao fim, a versão gravada MUST manter a mesma ordem.

#### Scenario: Texto depois de um gráfico
- **WHEN** a resposta tem texto, gráfico e mais texto
- **THEN** a página mostra os três nessa ordem durante a geração e depois de reabrir a conversa

#### Scenario: Exemplo do contrato
- **WHEN** o usuário abre a aba "Contrato de blocos"
- **THEN** o exemplo mostra um texto depois do gráfico
