# Tarefas

- [x] Implementar escopo obrigatório por entidade na validação SQL da fonte ODA.
- [x] Criar seed do catálogo com grupos, pesquisadores, linhas, setores e colunas permitidas.
- [x] Adicionar conexão e rede `maria_IA` ao compose de produção e ao `.env.example`.
- [x] Atualizar README e instruções de deploy.
- [ ] Validar o seed, o sincronismo do catálogo e consultas no ambiente Maria ligado ao ODA.
- [ ] Revisar a consulta com casos de CTE, junções e fontes com parceiros antes de habilitar a fonte em produção.

- [x] Alinhar instituições à regra SQL da API ODA e corrigir aliases e busca textual.
- [x] Validar enums físicos apenas para ODA e bloquear ODA no caminho federado.
- [x] Aplicar escopo às categorias observadas e apresentar pesquisadores sem consultar Simcc.
- [x] Cobrir o recorte e os erros reproduzidos com SQLite isolado; 93 testes de regressão e 19 subtestes aprovados na primeira rodada.
- [ ] Recriar o container de produção com a imagem corrigida e sincronizar novamente o catálogo.
