# Tasks

## 1. Copiar

- [x] 1.1 Em `demo/app.js`, adicionar o botão Copiar às respostas da Maria (D5), com confirmação e aviso de erro. Atualizar a seção **🎬 Demo** do README.

## 2. CSV

- [x] 2.1 Em `demo/app.js`, criar `toCsv` (D2, D3, D4) e os botões em `chart` e `table`. Verificar no navegador: BOM, `;`, vírgula decimal, aspas, fórmula neutralizada, número negativo intacto, título, aviso e origem no fim.

## 3. PNG

- [x] 3.1 Em `demo/app.js`, criar `chartPng` (D1) e o botão em `chart`. Verificar a imagem no navegador, com fundo, título, gráfico e origem.

## 4. Verificação integrada

- [x] 4.1 Rodar `poetry run task test` sem falhas e `openspec validate add-exportar-respostas --strict`.
- [x] 4.2 Com o modelo real, exportar uma resposta com gráfico e outra com tabela, em desktop e a 375px, e remover depois as conversas de teste.
