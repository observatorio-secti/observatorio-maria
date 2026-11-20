# Design

## Decisões

1. Consultar diretamente o PostgreSQL do ODA com `oda_leitura` pela rede externa `maria_IA`. Alternativa descartada: copiar dados para o SQLite da Maria, pois criaria sincronização e duplicação desnecessárias.
2. Aplicar política de linhas à árvore SQL já validada, para cada tabela ODA referenciada. Alternativa descartada: confiar somente no prompt ou nos exemplos, pois o modelo poderia omitir o filtro.
3. Usar o valor físico `sede` e reproduzir `shared/database/src/simcc.ts` do ODA: siglas SIMCC, prefixo `IFBA -` e FIOCRUZ com `Moniz` no nome. Alternativa descartada: busca ampla pelo nome, que incluiu fundações de apoio fora do recorte.
4. Expor apenas as tabelas e colunas necessárias para grupos, pesquisadores, linhas e setores. Alternativa descartada: sincronizar todo o schema ODA para o contexto.

## Política de escopo
- `grupo_pesquisa`: precisa ter vínculo `SEDE` com instituição SIMCC.
- `grupo_pesquisa_instituicao` e `instituicao`: somente sede e instituições da lista SIMCC.
- `membro_grupo` e `pesquisador`: somente membros de grupos elegíveis.
- `linha_pesquisa`, seus membros e seus setores: somente linhas pertencentes a grupos elegíveis.
- Qualquer tabela ODA fora da lista de políticas é recusada, mesmo que futuramente apareça no catálogo.

## Riscos
- [Risco] A rede externa não existir no host de deploy → Mitigação: validar `maria_IA` antes de subir o compose e documentar `ODA_NETWORK`.
- [Risco] Mudança do critério institucional → Mitigação: comparar com `shared/database/src/simcc.ts`; não acrescentar correspondências aproximadas por nome.
- [Risco] Alteração do schema do ODA → Mitigação: sincronizar o catálogo e manter entidades novas ocultas; a política falha fechada para tabelas desconhecidas.

## Migration Plan
Não há migração nem escrita no banco do ODA. A atualização do catálogo local da Maria é feita pelo seed e pela rota de sincronização; rollback consiste em remover a fonte `oda` do catálogo e desconectar a rede externa.

## Correções da auditoria
- Resolver busca textual no escopo original e validar literais de enums antes de injetar políticas. Alternativa descartada: converter todos os valores para minúsculas, pois outros enums têm rótulos maiúsculos válidos.
- Usar alias fixo privado da linha dentro de cada subconsulta; o alias do cliente existe apenas fora dela. Alternativa descartada: interpolar o alias do cliente nas políticas, que colidia com nomes internos.
- Bloquear consultas ODA federadas antes de qualquer conexão. Alternativa descartada: liberar ligações sem uma política equivalente no executor DuckDB.
- Filtrar categorias observadas pelo mesmo escopo e descartar valores antigos em falha. Alternativa descartada: manter categorias sem garantia de pertencerem ao recorte.
- Apresentar pesquisadores ODA como tabela do resultado. Alternativa descartada: hidratar no Simcc usando UUIDs de outra base.
