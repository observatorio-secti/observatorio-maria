## ADDED Requirements

### Requirement: Conceitos no prompt de sistema
Quando houver conceitos com entidades em pelo menos duas fontes incluídas, o prompt de sistema SHALL trazer a seção "Conceitos em várias fontes", com o mesmo texto da prévia de conceitos, antes dos contextos das fontes. Sem nenhum conceito nessas condições, a seção MUST ficar de fora.

#### Scenario: Fomento e Simcc com conceitos
- **WHEN** as fontes `fomento` e `simcc` estão ativas e o conceito `projetos` tem entidades nas duas
- **THEN** o prompt de sistema contém a seção de conceitos com a política de `projetos`, antes do contexto do fomento

#### Scenario: Uma fonte só
- **WHEN** só a fonte `fomento` está ativa
- **THEN** o prompt de sistema não contém a seção de conceitos
