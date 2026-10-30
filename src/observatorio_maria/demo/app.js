// Demo da API da Maria: consome os endpoints reais servidos pela mesma app.
const API_ROOT = new URL('..', window.location.href);

const state = { conversations: [], current: null, sending: false, abort: null };
const $ = (id) => document.getElementById(id);

// --- HTTP --------------------------------------------------------------------

async function apiError(response) {
  const body = await response.json().catch(() => ({}));
  const detail = Array.isArray(body.detail)
    ? body.detail.map((d) => d.msg).join('; ')
    : body.detail || response.statusText;
  const error = new Error(detail);
  error.status = response.status;
  return error;
}

async function api(path, options = {}) {
  const response = await fetch(new URL(path, API_ROOT), {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (response.status === 204) return null;
  if (!response.ok) throw await apiError(response);
  return response.json();
}

// Lê uma resposta Server-Sent Events de um POST (EventSource só faz GET).
async function* streamEvents(path, payload, signal) {
  const response = await fetch(new URL(path, API_ROOT), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
    body: JSON.stringify(payload),
    signal,
  });
  if (!response.ok) throw await apiError(response);

  const reader = response.body.pipeThrough(new TextDecoderStream()).getReader();
  let buffer = '';
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += value;
    const frames = buffer.split(/\r?\n\r?\n/);
    buffer = frames.pop();
    for (const frame of frames) {
      let event = 'message';
      const data = [];
      for (const line of frame.split(/\r?\n/)) {
        if (line.startsWith(':')) continue; // comentário (keep-alive)
        if (line.startsWith('event:')) event = line.slice(6).trim();
        else if (line.startsWith('data:')) data.push(line.slice(5).replace(/^ /, ''));
      }
      if (data.length) yield { event, data: JSON.parse(data.join('\n')) };
    }
  }
}

// --- Renderização de blocos (o mesmo código serve ao chat e ao exemplo) -------

function el(tag, attrs = {}, text) {
  const node = document.createElement(tag);
  Object.entries(attrs).forEach(([k, v]) => node.setAttribute(k, v));
  if (text !== undefined) node.textContent = text;
  return node;
}

function cssVar(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

const PALETTE = () => [1, 2, 3, 4, 5].map((i) => cssVar(`--chart-${i}`));

// Uma série: rótulo e unidade. Várias: só a unidade, se for a mesma em todas.
function chartYTitle(series) {
  if (series.length === 1) {
    const [{ label, unit }] = series;
    return unit ? `${label} (${unit})` : label;
  }
  const [{ unit }] = series;
  return unit && series.every((serie) => serie.unit === unit) ? unit : '';
}

function chartConfig(block, { text, grid }) {
  const yTitle = chartYTitle(block.series);
  const colors = PALETTE();
  const labels = block.data.map((row) => row[block.x.key]);
  const isPie = block.chart_type === 'pie';
  const datasets = block.series.map((serie, i) => ({
    label: serie.unit ? `${serie.label} (${serie.unit})` : serie.label,
    data:
      block.chart_type === 'scatter'
        ? block.data.map((row) => ({ x: row[block.x.key], y: row[serie.key] }))
        : block.data.map((row) => row[serie.key]),
    backgroundColor: isPie ? labels.map((_, j) => colors[j % colors.length]) : colors[i % colors.length],
    borderColor: colors[i % colors.length],
    fill: block.chart_type === 'area',
    tension: 0.25,
  }));
  return {
    type: block.chart_type === 'area' ? 'line' : block.chart_type,
    data: { labels, datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { labels: { color: text } } },
      scales: isPie
        ? {}
        : {
            x: { title: { display: true, text: block.x.label, color: text }, ticks: { color: text }, grid: { color: grid } },
            y: { title: { display: Boolean(yTitle), text: yTitle, color: text }, ticks: { color: text }, grid: { color: grid } },
          },
    },
  };
}

function truncationText(count) {
  return `Mostrando só as primeiras ${count} linhas: o resultado foi cortado pelo limite da consulta.`;
}

function truncationNotice(block, count) {
  return block.truncated ? el('p', { class: 'block-notice' }, truncationText(count)) : null;
}

function originText(origin) {
  const parts = [`Fonte: ${origin.sources.join(' e ')}`, origin.description];
  parts.push(`consultado em ${new Date(origin.queried_at).toLocaleDateString('pt-BR')}`);
  if (origin.coverage) {
    const { found, keys } = origin.coverage;
    parts.push(`${found.toLocaleString('pt-BR')} de ${keys.toLocaleString('pt-BR')} encontrados`);
  }
  return parts.join(' · ');
}

function originFooter(origin) {
  return origin ? el('p', { class: 'block-notice' }, originText(origin)) : null;
}

// --- Exportação ------------------------------------------------------------------

function saveFile(blob, title, extension) {
  const slug = title.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
  const link = el('a', { href: URL.createObjectURL(blob), download: `${slug || 'maria'}.${extension}` });
  link.click();
  URL.revokeObjectURL(link.href);
}

function csvCell(value) {
  if (value === null || value === undefined) return '';
  if (typeof value === 'number') return String(value).replace('.', ',');
  let text = String(value);
  // Dados de terceiros: não podem virar fórmula ao abrir na planilha.
  if (/^[=+\-@\t\r]/.test(text)) text = `'${text}`;
  return /[;"\r\n]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text;
}

function toCsv(columns, rows, block, count) {
  const lines = [
    columns.map((column) => csvCell(column.label)).join(';'),
    ...rows.map((row) => columns.map((column) => csvCell(row[column.key])).join(';')),
    '',
    csvCell(block.title ?? ''),
  ];
  if (block.truncated) lines.push(csvCell(truncationText(count)));
  if (block.origin) lines.push(csvCell(originText(block.origin)));
  return `\ufeff${lines.join('\r\n')}\r\n`;
}

function saveCsv(columns, rows, block) {
  const csv = toCsv(columns, rows, block, rows.length);
  saveFile(new Blob([csv], { type: 'text/csv;charset=utf-8' }), block.title ?? 'tabela', 'csv');
}

function wrapText(context, text, width) {
  const lines = [];
  let line = '';
  text.split(' ').forEach((word) => {
    const candidate = line ? `${line} ${word}` : word;
    if (context.measureText(candidate).width > width && line) {
      lines.push(line);
      line = word;
    } else {
      line = candidate;
    }
  });
  if (line) lines.push(line);
  return lines;
}

// Redesenha com o tema claro: o canvas da tela é transparente e usa as cores do tema.
function chartPng(block) {
  const width = 960;
  const height = 480;
  const margin = 24;
  const canvas = el('canvas', { width, height });
  const config = chartConfig(block, { text: '#344054', grid: '#e4e7ec' });
  config.options = { ...config.options, responsive: false, animation: false, devicePixelRatio: 1 };
  const chart = new Chart(canvas, config);

  const out = el('canvas', { width: width + margin * 2 });
  const context = out.getContext('2d');
  context.font = 'bold 20px sans-serif';
  const title = wrapText(context, block.title, width);
  context.font = '14px sans-serif';
  const notes = [block.truncated ? truncationText(block.data.length) : '', block.origin ? originText(block.origin) : '']
    .filter(Boolean)
    .flatMap((note) => wrapText(context, note, width));
  const top = margin + title.length * 26 + 8;
  out.height = top + height + notes.length * 20 + margin;

  context.fillStyle = '#ffffff';
  context.fillRect(0, 0, out.width, out.height);
  context.fillStyle = '#101828';
  context.font = 'bold 20px sans-serif';
  title.forEach((line, i) => context.fillText(line, margin, margin + 18 + i * 26));
  context.drawImage(canvas, margin, top, width, height);
  context.fillStyle = '#475467';
  context.font = '14px sans-serif';
  notes.forEach((line, i) => context.fillText(line, margin, top + height + 18 + i * 20));
  chart.destroy();
  out.toBlob((blob) => saveFile(blob, block.title, 'png'));
}

function exportActions(actions) {
  const bar = el('div', { class: 'block-actions' });
  actions.forEach(([label, run]) => {
    const button = el('button', { class: 'block-action', type: 'button' }, label);
    button.addEventListener('click', run);
    bar.append(button);
  });
  return bar;
}

async function copyMessage(message, button) {
  const text = message.content.filter((block) => block.type === 'text').map((block) => block.text).join('\n\n');
  try {
    await navigator.clipboard.writeText(text);
    button.textContent = 'Copiado';
    setTimeout(() => {
      button.textContent = 'Copiar';
    }, 1500);
  } catch {
    showBanner('Não foi possível copiar: o navegador não permitiu usar a área de transferência.');
  }
}

const blockRenderers = {
  text(block) {
    const node = el('div', { class: 'block block-text' });
    node.innerHTML = DOMPurify.sanitize(marked.parse(block.text));
    return node;
  },

  chart(block) {
    const node = el('div', { class: 'block block-chart' });
    node.append(el('h4', {}, block.title));
    const wrap = el('div', { class: 'canvas-wrap' });
    const canvas = el('canvas', { role: 'img', 'aria-label': block.title });
    wrap.append(canvas);
    node.append(wrap);
    const chartNotice = truncationNotice(block, block.data.length);
    if (chartNotice) node.append(chartNotice);
    const chartOrigin = originFooter(block.origin);
    if (chartOrigin) node.append(chartOrigin);
    const chartColumns = [block.x, ...block.series];
    node.append(
      exportActions([
        ['Baixar PNG', () => chartPng(block)],
        ['Baixar CSV', () => saveCsv(chartColumns, block.data, block)],
      ])
    );

    // O Chart.js precisa do canvas no DOM para medir; desenha no próximo frame.
    requestAnimationFrame(() => {
      new Chart(canvas, chartConfig(block, { text: cssVar('--muted'), grid: cssVar('--border') }));
    });
    return node;
  },

  table(block) {
    const node = el('div', { class: 'block block-table' });
    if (block.title) node.append(el('h4', {}, block.title));
    const table = el('table');
    const head = el('tr');
    block.columns.forEach((col) => head.append(el('th', {}, col.label)));
    const thead = el('thead');
    thead.append(head);
    table.append(thead);
    const body = el('tbody');
    block.rows.forEach((row) => {
      const tr = el('tr');
      block.columns.forEach((col) => {
        const value = row[col.key];
        const cell = el(
          'td',
          col.type === 'number' ? { class: 'num' } : {},
          col.type === 'number' && typeof value === 'number' ? value.toLocaleString('pt-BR') : value ?? '—'
        );
        tr.append(cell);
      });
      body.append(tr);
    });
    table.append(body);
    node.append(table);
    const tableNotice = truncationNotice(block, block.rows.length);
    if (tableNotice) node.append(tableNotice);
    const tableOrigin = originFooter(block.origin);
    if (tableOrigin) node.append(tableOrigin);
    node.append(exportActions([['Baixar CSV', () => saveCsv(block.columns, block.rows, block)]]));
    return node;
  },
};

function suggestionsBlock(block) {
  const node = el('div', { class: 'block block-suggestions' });
  block.questions.forEach((question) => {
    const button = el('button', { class: 'suggestion', type: 'button' }, question);
    button.addEventListener('click', () => {
      $('content').value = question;
      $('composer').requestSubmit();
    });
    node.append(button);
  });
  return node;
}

function renderBlocks(blocks) {
  const fragment = document.createDocumentFragment();
  blocks.forEach((block) => {
    if (block.type === 'suggestions') {
      fragment.append(suggestionsBlock(block));
      return;
    }
    const render = blockRenderers[block.type];
    // Tipos desconhecidos são ignorados; aqui mostramos um aviso só para a demo.
    fragment.append(
      render ? render(block) : el('div', { class: 'block block-unknown' }, `Bloco "${block.type}" ignorado (tipo desconhecido)`)
    );
  });
  return fragment;
}

function renderMessage(message, { pending = false } = {}) {
  const node = el('div', { class: `message ${message.role}${pending ? ' pending' : ''}` });
  node.append(renderBlocks(message.content));
  const time = message.created_at
    ? new Date(message.created_at).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })
    : 'enviando…';
  const meta = el('div', { class: 'meta' }, time);
  if (message.role === 'assistant' && message.created_at) {
    const copy = el('button', { class: 'block-action', type: 'button' }, 'Copiar');
    copy.addEventListener('click', () => copyMessage(message, copy));
    meta.append(' ', copy);
  }
  node.append(meta);
  return node;
}

// --- Status --------------------------------------------------------------------

async function loadStatus() {
  const apiPill = $('status-api');
  try {
    const health = await api('health');
    apiPill.textContent = `API ok · banco ${health.database}`;
    apiPill.className = 'pill ok';
  } catch {
    apiPill.textContent = 'API indisponível';
    apiPill.className = 'pill warn';
  }
}

// --- Conversas -------------------------------------------------------------------

function showBanner(message, retry) {
  const banner = $('banner');
  banner.textContent = message;
  banner.hidden = !message;
  if (!retry) return;
  const button = el('button', { class: 'banner-action', type: 'button' }, 'Tentar novamente');
  button.addEventListener('click', retry);
  banner.append(' ', button);
}

function setSending(sending) {
  state.sending = sending;
  $('send').textContent = sending ? 'Parar' : 'Enviar';
}

async function loadConversations() {
  const { conversations, total } = await api('conversations?limit=100');
  state.conversations = conversations;
  $('conversation-total').textContent = `${total} conversa${total === 1 ? '' : 's'}`;

  const list = $('conversation-list');
  list.replaceChildren();
  conversations.forEach((conversation) => {
    const item = el('li', conversation.id === state.current?.id ? { class: 'active' } : {});
    item.append(
      el('span', { class: conversation.title ? 'title' : 'title untitled' }, conversation.title || 'Nova conversa'),
      el('time', {}, new Date(conversation.updated_at).toLocaleString('pt-BR'))
    );
    item.addEventListener('click', () => openConversation(conversation.id));
    list.append(item);
  });
}

function showCurrentHeader() {
  $('chat-title').textContent = state.current
    ? state.current.title || 'Nova conversa'
    : 'Nova conversa';
  $('chat-actions').hidden = !state.current;
}

// --- Sugestões de perguntas --------------------------------------------------

const SUGGESTED_QUESTIONS = [
  'Quantas bolsas foram concedidas em cada modalidade em 2023?',
  'Quais as 5 instituições com mais bolsas?',
  'Como as bolsas se distribuem por grande área do conhecimento?',
  'Quantas bolsas estão ativas hoje?',
  'Como evoluiu o número de bolsas por ano desde 2018?',
  'Quantos projetos com bolsa tratam de agricultura familiar?',
  'Quantos bolsistas têm currículo Lattes identificado?',
  'Quantos artigos foram publicados por ano desde 2020?',
  'Quantos artigos Qualis A1 foram publicados desde 2022?',
  'Quais pesquisadores têm mais artigos?',
  'Que artigos tratam de inteligência artificial?',
  'Quantas patentes foram concedidas desde 2020?',
  'Quais instituições têm mais pesquisadores no Simcc?',
  'Que projetos de pesquisa do currículo Lattes tratam de educação?',
  'Quantos projetos sobre dengue existem?',
];
const SUGGESTIONS_SHOWN = 4;

// Sorteadas uma vez a cada acesso à página (Fisher-Yates).
const suggestions = [...SUGGESTED_QUESTIONS];
for (let i = suggestions.length - 1; i > 0; i -= 1) {
  const j = Math.floor(Math.random() * (i + 1));
  [suggestions[i], suggestions[j]] = [suggestions[j], suggestions[i]];
}
suggestions.length = SUGGESTIONS_SHOWN;

// Tela de conversa vazia: sai junto com `.empty` quando a conversa começa.
function emptyState(text) {
  const empty = el('div', { class: 'empty' });
  empty.append(el('p', {}, text));
  const list = el('div', { class: 'suggestions' });
  list.append(
    ...suggestions.map((question) => {
      const button = el('button', { class: 'suggestion', type: 'button' }, question);
      button.addEventListener('click', () => {
        $('content').value = question;
        $('composer').requestSubmit();
      });
      return button;
    })
  );
  empty.append(list);
  return empty;
}

async function openConversation(id) {
  showBanner('');
  state.current = await api(`conversations/${id}`);
  const { messages } = await api(`conversations/${id}/messages`);

  showCurrentHeader();

  const container = $('messages');
  container.replaceChildren();
  if (!messages.length) {
    container.append(emptyState('Nenhuma mensagem ainda. A primeira mensagem define o título.'));
  }
  messages.forEach((message) => container.append(renderMessage(message)));
  container.scrollTop = container.scrollHeight;
  await loadConversations();
  $('content').focus();
}

async function createConversation() {
  const conversation = await api('conversations', { method: 'POST', body: '{}' });
  await openConversation(conversation.id);
}

async function renameConversation() {
  const title = prompt('Novo título da conversa:', state.current.title || '');
  if (!title?.trim()) return;
  try {
    await api(`conversations/${state.current.id}`, {
      method: 'PATCH',
      body: JSON.stringify({ title: title.trim() }),
    });
    await openConversation(state.current.id);
  } catch (error) {
    showBanner(`Não foi possível renomear: ${error.message}`);
  }
}

async function deleteConversation() {
  if (!confirm('Excluir esta conversa e todas as mensagens?')) return;
  await api(`conversations/${state.current.id}`, { method: 'DELETE' });
  state.current = null;
  showCurrentHeader();
  $('messages').replaceChildren(emptyState('Conversa excluída. Escreva uma nova pergunta para começar outra.'));
  await loadConversations();
}

async function sendMessage(event) {
  event.preventDefault();
  const content = $('content').value.trim();
  if (!content || state.sending) return;

  setSending(true);
  state.abort = new AbortController();
  showBanner('');

  const container = $('messages');
  container.querySelector('.empty')?.remove();
  // Mensagem otimista: substituída pela versão persistida quando a API responde.
  const optimistic = renderMessage({ role: 'user', content: [{ type: 'text', text: content }] }, { pending: true });
  const typing = el('div', { class: 'message assistant typing', role: 'status' }, 'Maria está respondendo');
  container.append(optimistic, typing);
  container.scrollTop = container.scrollHeight;

  let userNode = optimistic;
  let partial = null; // balão com a resposta em geração
  let textPart = null; // texto em geração e o nó que o mostra
  try {
    // Sem conversa selecionada, a primeira mensagem cria uma nova.
    if (!state.current) {
      state.current = await api('conversations', { method: 'POST', body: '{}' });
      showCurrentHeader();
    }
    for await (const { event, data } of streamEvents(
      `conversations/${state.current.id}/messages/stream`,
      { content },
      state.abort.signal
    )) {
      if (event === 'message.user') {
        const node = renderMessage(data, { pending: true });
        userNode.replaceWith(node);
        userNode = node;
      } else if (event === 'activity') {
        typing.textContent = data.description || 'Maria está consultando os dados…';
        container.scrollTop = container.scrollHeight;
      } else if (event === 'content.delta') {
        if (!partial) {
          partial = el('div', { class: 'message assistant' });
          typing.replaceWith(partial);
        }
        // Anexa cada parte uma vez, para não recriar os gráficos já exibidos.
        if (data.type === 'text' && data.text) {
          const textBlock = { type: 'text', text: (textPart?.block.text ?? '') + data.text };
          const node = blockRenderers.text(textBlock);
          if (textPart) textPart.node.replaceWith(node);
          else partial.append(node);
          textPart = { block: textBlock, node };
        } else if (data.block) {
          textPart = null;
          partial.append(renderBlocks([data.block]));
        }
        container.scrollTop = container.scrollHeight;
      } else if (event === 'message.assistant') {
        // Versão persistida substitui o texto parcial; a pergunta também foi gravada.
        state.abort = null;
        userNode.classList.remove('pending');
        (partial ?? typing).replaceWith(renderMessage(data));
        partial = null;
      } else if (event === 'error') {
        const error = new Error(data.detail);
        error.status = 'stream';
        throw error;
      }
    }
    $('content').value = '';
    state.current = await api(`conversations/${state.current.id}`);
    showCurrentHeader();
    await loadConversations();
  } catch (error) {
    // Nada foi gravado: remove a pergunta e o texto parcial.
    userNode.remove();
    partial?.remove();
    if (error.name === 'AbortError') {
      showBanner('Resposta interrompida. Nada foi gravado na conversa.');
      return;
    }
    const hint =
      error.status === 429
        ? ' Use o botão "+ Nova conversa".'
        : error.status === 503
          ? ' Configure OPENAI_API_KEY no .env e reinicie a API.'
          : error.status === 'stream'
            ? ' Nada foi gravado na conversa; tente novamente.'
            : '';
    const status = typeof error.status === 'number' ? ` ${error.status}` : '';
    // A mensagem da API pode já terminar em ponto (limites da conversa).
    const message = error.message.replace(/[.\s]+$/, '');
    const retry = error.status === 429 || error.status === 503
      ? null
      : () => {
          $('content').value = content;
          $('composer').requestSubmit();
        };
    showBanner(`Erro${status}: ${message}.${hint}`, retry);
  } finally {
    typing.remove();
    state.abort = null;
    setSending(false);
    container.scrollTop = container.scrollHeight;
    $('content').focus();
  }
}

// --- Exemplo do contrato de blocos -----------------------------------------------

const SAMPLE_CONTENT = [
  {
    type: 'text',
    text: 'Entre **2021 e 2024** o número de bolsas cresceu de forma contínua. Os valores abaixo são *ilustrativos*:',
  },
  {
    type: 'chart',
    chart_type: 'bar',
    title: 'Bolsas de pesquisa concedidas por ano (exemplo)',
    x: { key: 'ano', label: 'Ano', type: 'category' },
    series: [
      { key: 'mestrado', label: 'Mestrado', unit: 'bolsas' },
      { key: 'doutorado', label: 'Doutorado', unit: 'bolsas' },
    ],
    data: [
      { ano: '2021', mestrado: 410, doutorado: 220 },
      { ano: '2022', mestrado: 455, doutorado: 248 },
      { ano: '2023', mestrado: 498, doutorado: 270 },
      { ano: '2024', mestrado: 530, doutorado: 301 },
    ],
    origin: {
      sources: ['Fomento à Pesquisa'],
      description: 'Bolsas por ano e modalidade',
      queried_at: '2026-10-23T08:00:00Z',
      coverage: null,
    },
  },
  { type: 'text', text: 'O **doutorado** cresceu menos em números absolutos. A distribuição por território vem a seguir:' },
  {
    type: 'table',
    title: 'Distribuição por território (exemplo)',
    columns: [
      { key: 'territorio', label: 'Território', type: 'string' },
      { key: 'bolsas', label: 'Bolsas', type: 'number' },
      { key: 'participacao', label: 'Participação (%)', type: 'number' },
    ],
    rows: [
      { territorio: 'Metropolitano de Salvador', bolsas: 512, participacao: 61.9 },
      { territorio: 'Portal do Sertão', bolsas: 118, participacao: 14.3 },
      { territorio: 'Litoral Sul', bolsas: 97, participacao: 11.7 },
      { territorio: 'Outros', bolsas: 104, participacao: 12.1 },
    ],
  },
  { type: 'map', region: 'BA', note: 'Tipo futuro: clientes atuais ignoram com segurança.' },
];

function renderSample() {
  $('sample-rendered').replaceChildren(renderBlocks(SAMPLE_CONTENT));
  $('sample-json').textContent = JSON.stringify({ role: 'assistant', content: SAMPLE_CONTENT }, null, 2);
}

// --- Abas e inicialização ----------------------------------------------------------

let sampleRendered = false;
document.querySelectorAll('.tab').forEach((tab) => {
  tab.addEventListener('click', () => {
    document.querySelectorAll('.tab').forEach((t) => t.classList.toggle('active', t === tab));
    document.querySelectorAll('.panel').forEach((p) => p.classList.toggle('active', p.id === `tab-${tab.dataset.tab}`));
    // Renderiza o exemplo só quando visível, para o Chart.js medir o canvas.
    if (tab.dataset.tab === 'blocks' && !sampleRendered) {
      renderSample();
      sampleRendered = true;
    }
  });
});

$('new-conversation').addEventListener('click', createConversation);
$('rename-conversation').addEventListener('click', renameConversation);
$('delete-conversation').addEventListener('click', deleteConversation);
$('composer').addEventListener('submit', sendMessage);
// Só o clique interrompe: Enter durante a geração continua sem efeito.
$('send').addEventListener('click', (event) => {
  if (!state.sending) return;
  event.preventDefault();
  state.abort?.abort();
});
$('content').addEventListener('keydown', (event) => {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault();
    $('composer').requestSubmit();
  }
});

$('messages').replaceChildren(
  emptyState('Escreva sua pergunta abaixo ou escolha uma sugestão. A conversa é criada e salva automaticamente.')
);
loadStatus();
loadConversations();
