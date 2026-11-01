# Tasks

## 1. Navegação por banco

- [x] 1.1 Trocar o seletor de fonte por abas geradas das fontes cadastradas, mais "Entre fontes", com cor por posição e indicação de fonte inativa, e verificar no navegador a troca entre Fomento e Simcc.
- [x] 1.2 Substituir a barra de ferramentas pelo cabeçalho do banco (nome, id, estado do schema, entidades em uso, datas, Verificar e Sincronizar) e verificar que ele permanece em todas as subabas.
- [x] 1.3 Mover "Fonte ativa", sincronização automática e "Baixar YAML" para a subaba Fonte e verificar que os três continuam funcionando.
- [x] 1.4 Mover conceitos, ligações e a prévia de conceitos para "Entre fontes", com o formulário de nova ligação em `<details>`, e verificar criar, editar e excluir conceito e ligação, desfazendo os dados de teste.

## 2. Essencial à vista

- [x] 2.1 Reduzir a lista de entidades às visíveis, com "Mostrar ocultas (N)", busca que alcança as ocultas e sem interruptor nas linhas, e verificar com o Simcc (94 entidades).
- [x] 2.2 Reorganizar a edição da entidade com "Usar nas respostas", rótulo, descrição e "Opções avançadas" (consultável, sinônimos, conceito), e verificar que ligar deixa a entidade visível e consultável, desfazendo a edição.
- [x] 2.3 Reduzir a tabela de colunas a nome, tipo, visível, descrição e "Opções", só com as visíveis por padrão e com "Mostrar ocultas (N)", e verificar a contagem numa entidade do Simcc.
- [x] 2.4 Levar acesso, pesquisável, valores no contexto e valores conhecidos para as opções da coluna, com selos dos ajustes fora do padrão e dos valores a revisar, e verificar que alterar o acesso muda a prévia, desfazendo a edição.

## 3. Avisos com ação

- [x] 3.1 Adicionar os avisos de fonte inativa e de sincronização automática ao cabeçalho e verificar que os botões resolvem o estado, restaurando a configuração original.
- [x] 3.2 Adicionar os avisos de entidade oculta e de entidade não consultável e verificar que os botões resolvem o estado, restaurando a configuração original.
- [x] 3.3 Adicionar o aviso de consultas entre fontes indisponíveis, com motivo e ação, e verificar os casos de fonte inativa e ligação desligada, restaurando a configuração original.
- [x] 3.4 Adicionar à ligação sem efeito os botões que abrem a entidade de cada ponta e verificar que levam ao banco certo com a entidade selecionada.

## 4. Documentação e verificação final

- [x] 4.1 Atualizar a seção Demo e o fluxo de nova fonte do `README.md` e conferir que todo controle citado existe na página.
- [x] 4.2 Verificar a aba no navegador a 1280px e a 375px, sem rolagem horizontal da página e sem erros no console, com a API local na porta 8001.
- [x] 4.3 Rodar `poetry run task test` sem falhas e `openspec validate repaginar-catalogo-demo --strict`, e conferir que `.env.example`, `chat.py` e os arquivos de cost-debug não entraram nesta mudança.

## 5. Tema claro

- [x] 5.1 Remover o tema escuro, suavizar os tokens de gráfico e tirar a seta de `/docs`, e verificar no navegador, com o sistema em modo escuro, que a página fica clara nas três abas, a 1280px e a 375px.
- [x] 5.2 Citar o tema claro na seção Demo do `README.md` e rodar `poetry run task test` e `openspec validate repaginar-catalogo-demo --strict` sem falhas.

## Workflow follow-up

- Arquivar a mudança depois da implementação, com os commits no padrão do projeto, separando as alterações pendentes de cost-debug.
