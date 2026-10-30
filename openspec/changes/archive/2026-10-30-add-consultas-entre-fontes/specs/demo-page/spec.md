## ADDED Requirements

### Requirement: Ligações entre fontes na página
A subaba "Conceitos" da aba do catálogo SHALL listar as ligações entre fontes, com indicação das que têm coluna ausente, e permitir criar, ligar, desligar e excluir ligações. Erros da API SHALL ser exibidos na aba.

#### Scenario: Desligar uma ligação
- **WHEN** o usuário desliga a ligação pelo Lattes
- **THEN** a prévia da seção deixa de mostrar "Consultas entre fontes"

#### Scenario: Ligação inválida
- **WHEN** o usuário cria uma ligação entre duas colunas da mesma fonte
- **THEN** a aba exibe a mensagem de erro da API
