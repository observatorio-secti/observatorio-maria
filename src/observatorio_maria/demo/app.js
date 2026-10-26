// Demo da API da Maria: consome os endpoints reais servidos pela mesma app.
const API_ROOT = new URL('..', window.location.href);

const state = { conversations: [], current: null, sending: false };
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
async function* streamEvents(path, payload) {
  const response = await fetch(new URL(path, API_ROOT), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
    body: JSON.stringify(payload),
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

    // O Chart.js precisa do canvas no DOM para medir; desenha no próximo frame.
    requestAnimationFrame(() => {
      const grid = cssVar('--border');
      const text = cssVar('--muted');
      new Chart(canvas, {
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
                y: { ticks: { color: text }, grid: { color: grid } },
              },
        },
      });
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
    return node;
  },
};

function renderBlocks(blocks) {
  const fragment = document.createDocumentFragment();
  blocks.forEach((block) => {
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
  node.append(el('div', { class: 'meta' }, time));
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

function showBanner(message) {
  const banner = $('banner');
  banner.textContent = message;
  banner.hidden = !message;
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

async function openConversation(id) {
  showBanner('');
  state.current = await api(`conversations/${id}`);
  const { messages } = await api(`conversations/${id}/messages`);

  showCurrentHeader();

  const container = $('messages');
  container.replaceChildren();
  if (!messages.length) {
    container.append(el('div', { class: 'empty' }, 'Nenhuma mensagem ainda. A primeira mensagem define o título.'));
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
  $('messages').replaceChildren(
    el('div', { class: 'empty' }, 'Conversa excluída. Escreva uma nova pergunta para começar outra.')
  );
  await loadConversations();
}

async function sendMessage(event) {
  event.preventDefault();
  const content = $('content').value.trim();
  if (!content || state.sending) return;

  state.sending = true;
  $('send').disabled = true;
  showBanner('');

  const container = $('messages');
  container.querySelector('.empty')?.remove();
  // Mensagem otimista: substituída pela versão persistida quando a API responde.
  const optimistic = renderMessage({ role: 'user', content: [{ type: 'text', text: content }] }, { pending: true });
  const typing = el('div', { class: 'message assistant typing', role: 'status' }, 'Maria está respondendo');
  container.append(optimistic, typing);
  container.scrollTop = container.scrollHeight;

  let userNode = optimistic;
  let partial = null; // balão com o texto em geração
  let text = '';
  const receivedBlocks = [];
  try {
    // Sem conversa selecionada, a primeira mensagem cria uma nova.
    if (!state.current) {
      state.current = await api('conversations', { method: 'POST', body: '{}' });
      showCurrentHeader();
    }
    for await (const { event, data } of streamEvents(`conversations/${state.current.id}/messages/stream`, {
      content,
    })) {
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
        if (data.type === 'text' && data.text) {
          text += data.text;
        } else if (data.block) {
          receivedBlocks.push(data.block);
        }
        const renderList = [];
        if (text) renderList.push({ type: 'text', text });
        renderList.push(...receivedBlocks);
        partial.replaceChildren(renderBlocks(renderList));
        container.scrollTop = container.scrollHeight;
      } else if (event === 'message.assistant') {
        // Versão persistida substitui o texto parcial; a pergunta também foi gravada.
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
    const hint =
      error.status === 429
        ? ' Crie uma nova conversa pelo botão "+ Nova conversa" para continuar.'
        : error.status === 503
          ? ' Configure OPENAI_API_KEY no .env e reinicie a API.'
          : error.status === 'stream'
            ? ' Nada foi gravado na conversa; tente novamente.'
            : '';
    const status = typeof error.status === 'number' ? ` ${error.status}` : '';
    showBanner(`Erro${status}: ${error.message}.${hint}`);
  } finally {
    typing.remove();
    state.sending = false;
    $('send').disabled = false;
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
  },
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
$('content').addEventListener('keydown', (event) => {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault();
    $('composer').requestSubmit();
  }
});

loadStatus();
loadConversations();
