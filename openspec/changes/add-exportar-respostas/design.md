# Design

## Context

Motivação em `proposal.md`. `blockRenderers` monta cada bloco e cria o `Chart` num `requestAnimationFrame`, sem guardar a instância. O canvas tem fundo transparente e cores do tema. A demo é um script clássico, sem etapa de build, e não tem suíte de JavaScript. `originFooter` já monta o texto da origem.

## Goals / Non-Goals

**Goals:**
- Arquivos legíveis fora da demo, com a procedência junto.
- Dados de terceiros não executam nada ao abrir o CSV.

**Non-Goals:**
- Reproduzir o tema da página nos arquivos: o PNG usa fundo claro fixo.

## Decisions

### D1. PNG composto num canvas novo

`chartPng` desenha fundo branco, título, o canvas do gráfico e a origem, com quebra de linha, e usa `toBlob`. Como os rótulos do tema escuro são claros, o gráfico é redesenhado com o tema claro numa instância temporária fora da tela.

Descartada: `chart.toBase64Image`, como previa o plano. A imagem sai transparente, sem título nem origem, e com texto claro ilegível em fundo branco.

### D2. CSV como função pura

`toCsv(columns, rows, footer)` recebe colunas e linhas já normalizadas, e `chart` e `table` adaptam seus dados a esse formato. Números usam vírgula decimal, sem separador de milhar.

Descartada: gerar a partir do DOM. A tabela na tela já tem números formatados e `—` nos vazios.

### D3. Metadados no fim do CSV

Título, aviso e origem ficam depois de uma linha em branco, no fim do arquivo.

Descartada: metadados no início. O Excel e outras ferramentas tomam a primeira linha como cabeçalho.

### D4. Proteção só em células de texto

Só strings recebem o prefixo `'`. Números são escritos sem prefixo, para `-5` continuar número.

Descartada: filtrar pelo primeiro caractere em todas as células. Números negativos virariam texto.

### D5. Copiar só o texto

`navigator.clipboard.writeText` recebe os blocos `text` em Markdown. Sem o `clipboard` (HTTP sem TLS, por exemplo), a página mostra um aviso.

Descartada: `document.execCommand`, obsoleto, que exigiria um elemento temporário e seleção.

## Risks / Trade-offs

- [Risco] Instância temporária do Chart.js custar tempo em gráficos grandes → Só ocorre no clique, e cada resultado tem no máximo `QUERY_MAX_ROWS` linhas.
- [Risco] Cópia indisponível em produção sem HTTPS → A página avisa, e a seleção manual continua funcionando.
- [Risco] Apóstrofo aparecer em células legítimas que começam com `-` → É o custo aceito da proteção; o dado segue legível.
