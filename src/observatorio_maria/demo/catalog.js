// Aba "Catálogo de dados": configura o que a Maria enxerga e pode consultar.
// Reaproveita `api`, `el` e `$` de app.js (scripts clássicos compartilham o escopo global).

const catalog = {
  datasources: [],
  datasource: null,
  entities: [],
  entity: null,
  view: 'entity',
  concepts: [],
  editingConcept: null, // id do conceito em edição; '' para um novo
  loaded: false,
  expanded: new Set(), // colunas com o editor de valores aberto
};

const KIND_LABELS = { table: 'tabela', view: 'view', materialized_view: 'view materializada' };

const SCHEMA_STATUS = {
  up_to_date: ['Schema em dia', 'ok'],
  outdated: ['Schema desatualizado', 'warn'],
  error: ['Erro na verificação', 'error'],
  unknown: ['Schema não verificado', ''],
};

const DRIFT_SECTIONS = [
  ['added_entities', 'Entidades novas (entram ocultas)'],
  ['missing_entities', 'Entidades removidas da origem'],
  ['added_columns', 'Colunas novas (entram ocultas)'],
  ['missing_columns', 'Colunas removidas da origem'],
  ['changed_columns', 'Colunas alteradas'],
  ['new_enum_values', 'Valores de enum novos'],
  ['removed_enum_values', 'Valores de enum removidos'],
];

const formatDate = (value) => new Date(value).toLocaleString('pt-BR');

const nullable = (value) => (value.trim() === '' ? null : value.trim());
const splitList = (value) => value.split(',').map((s) => s.trim()).filter(Boolean);

function catalogError(message) {
  const banner = $('cat-banner');
  banner.textContent = message;
  banner.hidden = !message;
}

// Executa uma ação da API e mostra o erro na aba, sem derrubar a tela.
async function attempt(action) {
  try {
    const result = await action();
    catalogError('');
    return result;
  } catch (error) {
    catalogError(error.message);
    return undefined;
  }
}

function flash(id, text = 'Salvo') {
  const node = $(id);
  node.textContent = text;
  setTimeout(() => { if (node.textContent === text) node.textContent = ''; }, 2000);
}

function switchInput(checked, onChange, { disabled = false, label } = {}) {
  const wrap = el('label', { class: 'switch' });
  const input = el('input', { type: 'checkbox' });
  if (label) input.setAttribute('aria-label', label);
  input.checked = checked;
  input.disabled = disabled;
  input.addEventListener('click', (event) => event.stopPropagation());
  input.addEventListener('change', () => onChange(input.checked, input));
  wrap.append(input);
  return wrap;
}

function badge(text, kind = '') {
  return el('span', { class: `badge ${kind}`.trim() }, text);
}

// --- Fonte de dados ----------------------------------------------------------

function base() {
  return `catalog/datasources/${encodeURIComponent(catalog.datasource.id)}`;
}

async function loadDatasources() {
  const data = await attempt(() => api('catalog/datasources'));
  if (!data) return;
  catalog.datasources = data.datasources;
  const select = $('cat-datasource');
  select.replaceChildren(...data.datasources.map((d) => el('option', { value: d.id }, d.name)));
  $('cat-empty').hidden = data.datasources.length > 0;
  $('cat-layout').hidden = data.datasources.length === 0;
  document.querySelector('.catalog-toolbar').hidden = data.datasources.length === 0;
  if (data.datasources.length) await selectDatasource(catalog.datasource?.id ?? data.datasources[0].id);
}

function renderDatasource() {
  const d = catalog.datasource;
  $('cat-datasource').value = d.id;
  $('cat-enabled').checked = d.enabled;
  $('cat-auto-sync').checked = d.auto_sync;
  const synced = d.last_synced_at ? `sincronizada em ${formatDate(d.last_synced_at)}` : 'nunca sincronizada';
  const checked = d.last_checked_at ? `verificada em ${formatDate(d.last_checked_at)}` : 'nunca verificada';
  $('cat-summary').textContent =
    `${d.entities_total} entidades · ${d.entities_visible} visíveis · ` +
    `${d.entities_queryable} consultáveis · ${synced} · ${checked} · conexão em ${d.connection_env}`;
  const [label, kind] = SCHEMA_STATUS[d.schema_status] ?? SCHEMA_STATUS.unknown;
  const pill = $('cat-schema-status');
  pill.textContent = label;
  pill.className = `pill ${kind}`.trim();
  renderDrift();
  $('cat-export').href = new URL(`${base()}/export`, API_ROOT);

  const form = $('view-source');
  form.name.value = d.name;
  form.connection_env.value = d.connection_env;
  form.description.value = d.description ?? '';
  form.instructions.value = d.instructions ?? '';
}

async function selectDatasource(id) {
  const datasource = await attempt(() => api(`catalog/datasources/${encodeURIComponent(id)}`));
  if (!datasource) return;
  if (catalog.datasource?.id !== id) {
    catalog.entity = null;
    $('cat-report').hidden = true;
  }
  catalog.datasource = datasource;
  renderDatasource();
  await loadEntities();
  await refreshView();
}

async function refreshSummary() {
  const datasource = await attempt(() => api(base()));
  if (datasource) {
    catalog.datasource = datasource;
    renderDatasource();
  }
}

async function patchDatasource(changes) {
  const datasource = await attempt(() => api(base(), { method: 'PATCH', body: JSON.stringify(changes) }));
  if (datasource) {
    catalog.datasource = datasource;
    renderDatasource();
    if (catalog.view === 'context') await refreshView();
  }
  return datasource;
}

function renderDrift() {
  const d = catalog.datasource;
  const card = $('cat-drift');
  card.classList.toggle('error', d.schema_status === 'error');
  card.hidden = !['outdated', 'error'].includes(d.schema_status);
  if (card.hidden) return;

  if (d.schema_status === 'error') {
    card.replaceChildren(
      el('strong', {}, 'Não foi possível verificar a origem.'),
      el('p', {}, d.check_error ?? 'Erro desconhecido.')
    );
    return;
  }

  card.replaceChildren(el('strong', {}, 'A origem mudou desde a última sincronização.'));
  const drift = d.drift ?? {};
  let shown = 0;
  DRIFT_SECTIONS.forEach(([key, title]) => {
    const items = drift[key] ?? [];
    if (!items.length) return;
    shown += items.length;
    card.append(el('p', {}, `${title}: ${items.length}`));
    const list = el('ul');
    items.slice(0, 10).forEach((item) => list.append(el('li', {}, item)));
    if (items.length > 10) list.append(el('li', {}, `… e mais ${items.length - 10}`));
    card.append(list);
  });
  const links = (drift.added_relationships ?? 0) + (drift.missing_relationships ?? 0);
  if (links) {
    shown += links;
    card.append(el('p', {}, `Relacionamentos: ${drift.added_relationships} novo(s), ${drift.missing_relationships} removido(s)`));
  }
  if (!shown) {
    card.append(
      el('p', {}, 'Nenhuma entidade ou coluna mudou: a diferença é de detalhes técnicos (por exemplo, a primeira leitura dos valores de enum). Sincronize para registrar.')
    );
  }
  const button = el('button', { class: 'primary' }, 'Sincronizar agora');
  button.addEventListener('click', syncDatasource);
  card.append(button);
}

async function checkDatasource() {
  const button = $('cat-check');
  button.disabled = true;
  button.textContent = 'Verificando…';
  const result = await attempt(() => api(`${base()}/check`, { method: 'POST' }));
  button.disabled = false;
  button.textContent = 'Verificar agora';
  if (!result) return;
  if (result.sync) showSyncReport(result.sync, 'Sincronizado automaticamente');
  else $('cat-report').hidden = true;
  await selectDatasource(catalog.datasource.id);
}

async function syncDatasource() {
  const button = $('cat-sync');
  button.disabled = true;
  button.textContent = 'Sincronizando…';
  const report = await attempt(() => api(`${base()}/sync`, { method: 'POST' }));
  button.disabled = false;
  button.textContent = 'Sincronizar schema';
  if (!report) return;
  showSyncReport(report, 'Sincronizado');
  await selectDatasource(catalog.datasource.id);
}

function showSyncReport(report, title) {
  const box = $('cat-report');
  const lines = [
    ['Entidades novas (entram ocultas)', report.added_entities],
    ['Entidades ausentes na origem', report.missing_entities],
    ['Colunas novas (entram ocultas)', report.added_columns],
    ['Colunas ausentes na origem', report.missing_columns],
    ['Valores de enum novos (sem descrição)', report.new_enum_values],
  ].filter(([, items]) => items.length);
  box.replaceChildren(
    el(
      'strong',
      {},
      `${title} às ${new Date(report.synced_at).toLocaleTimeString('pt-BR')}: ` +
        `${report.added_relationships} relacionamento(s) novo(s), ${report.missing_relationships} ausente(s).`
    )
  );
  if (!lines.length) box.append(el('p', { class: 'muted' }, 'Nenhuma mudança de entidades ou colunas.'));
  lines.forEach(([title, items]) => {
    box.append(el('p', {}, `${title}: ${items.length}`));
    const list = el('ul');
    items.slice(0, 12).forEach((item) => list.append(el('li', {}, item)));
    if (items.length > 12) list.append(el('li', { class: 'muted' }, `… e mais ${items.length - 12}`));
    box.append(list);
  });
  box.hidden = false;
}

// --- Entidades ---------------------------------------------------------------

async function loadEntities() {
  const data = await attempt(() => api(`${base()}/entities`));
  if (!data) return;
  catalog.entities = data.entities;
  renderEntityList();
  if (catalog.entity) await selectEntity(catalog.entity.id);
  else renderEntity();
}

function entityMatches(entity) {
  const filter = $('cat-filter').value;
  const term = $('cat-search').value.trim().toLowerCase();
  if (filter === 'visible' && !entity.visible) return false;
  if (filter === 'hidden' && entity.visible) return false;
  if (filter === 'missing' && entity.present) return false;
  return !term || `${entity.name} ${entity.label ?? ''}`.toLowerCase().includes(term);
}

function renderEntityList() {
  const list = $('cat-entities');
  const items = catalog.entities.filter(entityMatches).map((entity) => {
    const li = el('li', {
      class: [entity.id === catalog.entity?.id && 'active', !entity.visible && 'is-hidden'].filter(Boolean).join(' '),
    });
    const name = el('div', { class: 'entity-name' });
    name.append(el('strong', {}, entity.label ?? entity.name));
    const kind = KIND_LABELS[entity.kind] ?? 'sem sincronizar';
    name.append(el('small', {}, `${entity.name} · ${kind}${entity.queryable ? ' · consultável' : ''}`));
    li.append(name);
    if (!entity.present) li.append(badge('ausente', 'warn'));
    li.append(
      switchInput(entity.visible, (checked) => patchEntity(entity.id, { visible: checked }), {
        label: `Visível: ${entity.name}`,
      })
    );
    li.addEventListener('click', () => selectEntity(entity.id, { show: true }));
    return li;
  });
  list.replaceChildren(...(items.length ? items : [el('li', { class: 'muted' }, 'Nenhuma entidade.')]));
}

async function selectEntity(id, { show = false } = {}) {
  const entity = await attempt(() => api(`catalog/entities/${id}`));
  if (!entity) return;
  catalog.entity = entity;
  renderEntityList();
  renderEntity();
  if (show) showView('entity');
}

function renderEntity() {
  const entity = catalog.entity;
  const form = $('cat-entity-form');
  $('cat-entity-empty').hidden = Boolean(entity);
  form.hidden = !entity;
  if (!entity) return;

  $('cat-entity-title').textContent = `${entity.schema_name}.${entity.name}`;
  $('cat-entity-badges').replaceChildren(
    badge(KIND_LABELS[entity.kind] ?? 'sem sincronizar'),
    entity.present ? badge('presente na origem', 'ok') : badge('ausente na origem', 'warn'),
    badge(`${entity.columns_visible}/${entity.columns_total} colunas visíveis`)
  );
  form.visible.checked = entity.visible;
  form.queryable.checked = entity.queryable;
  form.queryable.disabled = !entity.visible; // consultável exige visível
  form.label.value = entity.label ?? '';
  form.synonyms.value = entity.synonyms.join(', ');
  renderConceptOptions();
  form.concept_id.value = entity.concept_id ?? '';
  form.description.value = entity.description ?? '';

  $('cat-columns').replaceChildren(...entity.columns.flatMap(renderColumnRows));
}

// Valores da origem: os do enum ou, sem enum, os observados nos dados.
const sourceValues = (column) => column.enum_values ?? column.observed_values ?? null;

// Valores conhecidos: os da origem (na ordem dela) mais os informados que não
// existem nela (obsoletos); sem valores da origem, os valores editoriais.
function valueRows(column) {
  const descriptions = new Map(column.values.map((v) => [String(v.value), v.description ?? '']));
  const values = sourceValues(column) ?? column.values.map((v) => String(v.value));
  const rows = values.map((value) => ({ value, description: descriptions.get(value) ?? '', obsolete: false }));
  column.obsolete_values.forEach((value) => rows.push({ value, description: descriptions.get(value) ?? '', obsolete: true }));
  return rows;
}

function renderValuesEditor(column) {
  const editor = el('div', { class: 'values-editor' });
  const inputs = [];
  valueRows(column).forEach((row) => {
    const code = el('code', {}, row.value);
    const input = el('input', { 'aria-label': `Descrição do valor ${row.value}`, placeholder: 'Significado do valor…' });
    input.value = row.description;
    const status = el('span');
    if (row.obsolete) {
      status.append(badge('obsoleto', 'warn'), ' ');
      const remove = el('button', { type: 'button', class: 'link' }, 'remover');
      remove.addEventListener('click', () => {
        inputs.splice(inputs.findIndex((i) => i.row === row), 1);
        code.remove(); input.remove(); status.remove();
      });
      status.append(remove);
    } else if (!row.description && sourceValues(column)) {
      status.append(badge('sem descrição', 'warn'));
    }
    inputs.push({ row, input });
    editor.append(code, input, status);
  });

  const actions = el('div', { class: 'actions' });
  const save = el('button', { type: 'button', class: 'primary' }, 'Salvar valores');
  save.addEventListener('click', () => {
    const values = inputs
      .map(({ row, input }) => ({ value: row.value, description: nullable(input.value) }))
      // Valor da origem sem descrição não precisa ser guardado: ele já vem dela.
      .filter((v) => !sourceValues(column) || v.description || !sourceValues(column).includes(v.value));
    patchColumn(column, { values });
  });
  const origin = column.enum_values
    ? 'Valores lidos do enum da origem.'
    : column.observed_values
      ? 'Valores lidos dos dados da origem.'
      : 'Valores informados no catálogo.';
  actions.append(save, el('span', { class: 'muted small' }, origin));
  editor.append(actions);
  return editor;
}

function renderColumnRows(column) {
  const rows = [renderColumnRow(column)];
  if (catalog.expanded.has(column.id)) {
    const tr = el('tr', { class: 'values-row' });
    const td = el('td', { colspan: 6 });
    td.append(renderValuesEditor(column));
    tr.append(td);
    rows.push(tr);
  }
  return rows;
}

function renderColumnRow(column) {
  const tr = el('tr', column.present ? {} : { class: 'is-missing' });
  const name = el('td', { class: 'mono' }, column.name);
  if (column.primary_key) name.append(el('span', { class: 'key', title: 'Chave primária' }, 'PK'));
  if (!column.present) name.append(' ', badge('ausente', 'warn'));
  const known = valueRows(column).length;
  if (known) {
    const pending = column.undescribed_values.length + column.obsolete_values.length;
    const toggle = el(
      'button',
      { type: 'button', class: 'values-toggle', 'aria-expanded': String(catalog.expanded.has(column.id)) },
      `valores (${known})`
    );
    toggle.addEventListener('click', () => {
      if (catalog.expanded.has(column.id)) catalog.expanded.delete(column.id);
      else catalog.expanded.add(column.id);
      renderEntity();
    });
    name.append(toggle);
    if (pending) name.append(' ', badge(`${pending} a revisar`, 'warn'));
  }
  tr.append(name, el('td', { class: 'mono' }, column.data_type ?? '—'));

  const visible = el('td');
  visible.append(
    switchInput(column.visible, (checked) => patchColumn(column, { visible: checked }), {
      label: `Visível: ${column.name}`,
    })
  );

  const access = el('select', { 'aria-label': `Acesso: ${column.name}` });
  access.append(el('option', { value: 'full' }, 'Valores'), el('option', { value: 'aggregate' }, 'Só agregação'));
  access.value = column.access;
  access.addEventListener('change', () => patchColumn(column, { access: access.value }));
  const accessCell = el('td');
  accessCell.append(access);

  const searchable = el('td');
  searchable.append(
    switchInput(column.searchable, (checked) => patchColumn(column, { searchable: checked }), {
      label: `Pesquisável: ${column.name}`,
    })
  );

  const description = el('input', {
    'aria-label': `Descrição: ${column.name}`,
    placeholder: column.label ?? 'Descreva a coluna…',
  });
  description.value = column.description ?? '';
  description.addEventListener('change', () => patchColumn(column, { description: nullable(description.value) }));
  const descriptionCell = el('td');
  descriptionCell.append(description);

  tr.append(visible, accessCell, searchable, descriptionCell);
  return tr;
}

async function patchEntity(id, changes) {
  const entity = await attempt(() => api(`catalog/entities/${id}`, { method: 'PATCH', body: JSON.stringify(changes) }));
  if (entity) {
    const index = catalog.entities.findIndex((e) => e.id === id);
    if (index >= 0) catalog.entities[index] = entity;
    if (catalog.entity?.id === id) catalog.entity = entity;
    await refreshSummary();
  }
  // Também no erro: volta os interruptores para o estado real.
  renderEntityList();
  renderEntity();
  if (catalog.view !== 'entity') await refreshView();
  return entity;
}

async function patchColumn(column, changes) {
  const updated = await attempt(() =>
    api(`catalog/columns/${column.id}`, { method: 'PATCH', body: JSON.stringify(changes) })
  );
  if (catalog.entity) await selectEntity(catalog.entity.id);
  if (updated) flash('cat-entity-saved', `Coluna ${column.name} salva`);
}

// --- Relacionamentos, prévia e visões ----------------------------------------

async function loadRelationships() {
  const data = await attempt(() => api(`${base()}/relationships`));
  if (!data) return;
  const rows = data.relationships.map((r) => {
    const tr = el('tr', r.present ? {} : { class: 'is-missing' });
    const enabled = el('td');
    enabled.append(
      switchInput(r.enabled, (checked) => patchRelationship(r.id, { enabled: checked }), {
        label: `Ligado: ${r.from_entity}`,
      })
    );
    const origin = el('td');
    origin.append(badge(r.origin === 'foreign_key' ? 'chave estrangeira' : 'manual'));
    if (!r.present) origin.append(' ', badge('ausente', 'warn'));
    const description = el('input', { 'aria-label': 'Descrição do relacionamento' });
    description.value = r.description ?? '';
    description.addEventListener('change', () => patchRelationship(r.id, { description: nullable(description.value) }));
    const descriptionCell = el('td');
    descriptionCell.append(description);
    tr.append(
      enabled,
      el('td', { class: 'mono' }, `${r.from_entity}.${r.from_columns.join(', ')}`),
      el('td', { class: 'mono' }, `${r.to_entity}.${r.to_columns.join(', ')}`),
      origin,
      descriptionCell
    );
    return tr;
  });
  if (!rows.length) {
    const empty = el('tr');
    empty.append(el('td', { colspan: 5, class: 'muted' }, 'Nenhum relacionamento. Sincronize a fonte.'));
    rows.push(empty);
  }
  $('cat-relationships').replaceChildren(...rows);
}

async function patchRelationship(id, changes) {
  await attempt(() => api(`catalog/relationships/${id}`, { method: 'PATCH', body: JSON.stringify(changes) }));
  await loadRelationships();
}

async function loadContext() {
  const data = await attempt(() => api(`${base()}/context`));
  if (!data) return;
  $('cat-context').textContent = data.enabled
    ? data.content
    : 'Fonte desativada: o modelo não recebe nada sobre ela.';
  renderRejectedExamples(data.enabled ? data.rejected_examples : []);
}

// Exemplos few-shot que não passam nas regras de consulta ficam fora do texto.
function renderRejectedExamples(rejected) {
  const box = $('cat-rejected-examples');
  box.hidden = !rejected.length;
  if (!rejected.length) return box.replaceChildren();
  const items = rejected.map((r) => {
    const li = el('li');
    li.append(el('strong', {}, r.question), ': ', r.reason);
    return li;
  });
  const list = el('ul');
  list.append(...items);
  box.replaceChildren(el('strong', {}, `${rejected.length} exemplo(s) fora do contexto`), list);
}

// --- Conceitos ----------------------------------------------------------------

async function loadConcepts() {
  const data = await attempt(() => api('catalog/concepts'));
  if (!data) return;
  catalog.concepts = data.concepts;
  renderConcepts();
  renderConceptOptions();
}

function renderConceptOptions() {
  const select = $('cat-entity-form').concept_id;
  const current = select.value;
  select.replaceChildren(
    el('option', { value: '' }, 'Nenhum'),
    ...catalog.concepts.map((c) => el('option', { value: c.id }, c.label))
  );
  select.value = current;
}

function renderConcepts() {
  const items = catalog.concepts.map((concept) => {
    const li = el('li');
    const head = el('div', { class: 'concept-head' });
    head.append(el('strong', {}, concept.label), el('small', { class: 'muted mono' }, concept.id));
    const actions = el('div', { class: 'actions' });
    const edit = el('button', { class: 'ghost', type: 'button' }, 'Editar');
    edit.addEventListener('click', () => editConcept(concept.id));
    const remove = el('button', { class: 'ghost', type: 'button' }, 'Excluir');
    remove.addEventListener('click', () => deleteConcept(concept));
    actions.append(edit, remove);
    head.append(actions);
    const entities = el('div', { class: 'concept-entities' });
    entities.append(
      ...(concept.entities.length
        ? concept.entities.map((e) => badge(`${e.datasource_id}: ${e.schema_name}.${e.name}`))
        : [el('span', { class: 'muted small' }, 'Nenhuma entidade vinculada.')])
    );
    li.append(head, entities);
    if (concept.description) li.append(el('p', { class: 'muted small' }, concept.description));
    return li;
  });
  $('cat-concepts').replaceChildren(...(items.length ? items : [el('li', { class: 'muted' }, 'Nenhum conceito.')]));
}

function editConcept(id) {
  const concept = catalog.concepts.find((c) => c.id === id);
  const form = $('cat-concept-form');
  catalog.editingConcept = id ?? '';
  form.hidden = false;
  $('cat-concept-title').textContent = concept ? `Editar ${concept.label}` : 'Novo conceito';
  form.id.value = concept?.id ?? '';
  form.id.disabled = Boolean(concept); // o identificador não muda
  form.label.value = concept?.label ?? '';
  form.synonyms.value = concept?.synonyms.join(', ') ?? '';
  form.description.value = concept?.description ?? '';
  form.instructions.value = concept?.instructions ?? '';
  (concept ? form.label : form.id).focus();
}

function closeConceptForm() {
  catalog.editingConcept = null;
  $('cat-concept-form').hidden = true;
}

async function loadConceptsContext() {
  const data = await attempt(() => api('catalog/concepts/context'));
  if (!data) return;
  $('cat-concepts-context').textContent =
    data.content ||
    'Nenhum conceito tem entidades visíveis em duas ou mais fontes ativas: a seção não entra no prompt.';
}

async function saveConcept(event) {
  event.preventDefault();
  const form = event.target;
  const changes = {
    label: form.label.value.trim(),
    synonyms: splitList(form.synonyms.value),
    description: nullable(form.description.value),
    instructions: nullable(form.instructions.value),
  };
  const id = catalog.editingConcept;
  const saved = await attempt(() =>
    id
      ? api(`catalog/concepts/${encodeURIComponent(id)}`, { method: 'PATCH', body: JSON.stringify(changes) })
      : api('catalog/concepts', { method: 'POST', body: JSON.stringify({ id: form.id.value.trim(), ...changes }) })
  );
  if (!saved) return;
  flash('cat-concept-saved');
  closeConceptForm();
  await loadConcepts();
  await loadConceptsContext();
}

async function deleteConcept(concept) {
  if (!confirm(`Excluir o conceito "${concept.label}"? As entidades ficam sem conceito.`)) return;
  const deleted = await attempt(async () => {
    await api(`catalog/concepts/${encodeURIComponent(concept.id)}`, { method: 'DELETE' });
    return true;
  });
  if (!deleted) return;
  if (catalog.editingConcept === concept.id) closeConceptForm();
  await loadConcepts();
  await loadConceptsContext();
  if (catalog.entity) await selectEntity(catalog.entity.id);
}

function showView(view) {
  catalog.view = view;
  document.querySelectorAll('.subtab').forEach((t) => t.classList.toggle('active', t.dataset.view === view));
  document.querySelectorAll('#tab-catalog .view').forEach((v) => v.classList.toggle('active', v.id === `view-${view}`));
}

async function refreshView() {
  if (catalog.view === 'relationships') await loadRelationships();
  if (catalog.view === 'context') await loadContext();
  if (catalog.view === 'concepts') {
    await loadConcepts();
    await loadConceptsContext();
  }
}

// --- Eventos -----------------------------------------------------------------

document.querySelectorAll('.subtab').forEach((tab) => {
  tab.addEventListener('click', async () => {
    showView(tab.dataset.view);
    await refreshView();
  });
});

$('cat-datasource').addEventListener('change', (event) => selectDatasource(event.target.value));
$('cat-enabled').addEventListener('change', (event) => patchDatasource({ enabled: event.target.checked }));
$('cat-sync').addEventListener('click', syncDatasource);
$('cat-check').addEventListener('click', checkDatasource);
$('cat-auto-sync').addEventListener('change', (event) => patchDatasource({ auto_sync: event.target.checked }));
$('cat-search').addEventListener('input', renderEntityList);
$('cat-filter').addEventListener('change', renderEntityList);

const entityForm = $('cat-entity-form');
entityForm.visible.addEventListener('change', () => patchEntity(catalog.entity.id, { visible: entityForm.visible.checked }));
entityForm.queryable.addEventListener('change', () =>
  patchEntity(catalog.entity.id, { queryable: entityForm.queryable.checked })
);
entityForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  const saved = await patchEntity(catalog.entity.id, {
    label: nullable(entityForm.label.value),
    description: nullable(entityForm.description.value),
    synonyms: splitList(entityForm.synonyms.value),
    concept_id: entityForm.concept_id.value || null,
  });
  if (saved) {
    flash('cat-entity-saved');
    await loadConcepts();
  }
});

$('cat-concept-new').addEventListener('click', () => editConcept(null));
$('cat-concept-cancel').addEventListener('click', closeConceptForm);
$('cat-concept-form').addEventListener('submit', saveConcept);

$('view-source').addEventListener('submit', async (event) => {
  event.preventDefault();
  const form = event.target;
  const saved = await patchDatasource({
    name: form.name.value.trim(),
    connection_env: form.connection_env.value.trim(),
    description: nullable(form.description.value),
    instructions: nullable(form.instructions.value),
  });
  if (saved) {
    flash('cat-source-saved');
    const option = $('cat-datasource').querySelector(`option[value="${saved.id}"]`);
    if (option) option.textContent = saved.name;
  }
});

// Carrega na primeira vez que a aba é aberta.
document.querySelector('.tab[data-tab="catalog"]').addEventListener('click', () => {
  if (!catalog.loaded) {
    catalog.loaded = true;
    loadConcepts().then(loadDatasources);
  }
});
