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

## Correções após o merge
- [x] Reparar a sintaxe de `_policy`, preservar a implementação por dicionário e o enum físico `sede`.
- [x] Resolver aliases por escopo ODA na proteção de colunas somente para agregação.
- [x] Validar busca em todos os ramos UNION, incluindo a recusa de expressões sem origem pesquisável garantida.
- [x] Validar enums em COALESCE e CASE e aceitar CASE válido na fonte ODA.
- [x] Limpar categorias ODA quando a conexão falha antes da leitura, preservando o comportamento das demais fontes.
- [x] Incluir o seed ODA no entrypoint e preservar LF pelo Git.
- [x] Executar lint completo, conferir sintaxe do shell e rodar a suíte completa em container isolado: 652 testes aprovados e 91% de cobertura.
- [x] Atualizar README, guia de deploy e especificações correspondentes.
