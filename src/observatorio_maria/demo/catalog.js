// Aba "Catálogo de dados": configura o que a Maria enxerga e pode consultar.
// Reaproveita `api`, `el` e `$` de app.js (scripts clássicos compartilham o escopo global).

const catalog = {
  datasources: [],
  area: null, // id da fonte aberta ou SHARED_AREA
  datasource: null,
  entities: [],
  entity: null,
  showHidden: false, // lista as entidades ocultas
  showHiddenColumns: false, // lista as colunas ocultas
  touchedColumns: new Set(), // colunas ocultadas agora seguem à vista até trocar de entidade
  view: 'entity',
  concepts: [],
  editingConcept: null, // id do conceito em edição; '' para um novo
  loaded: false,
  expanded: new Set(), // colunas com as opções abertas
};

const SHARED_AREA = 'shared';

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

function actionButton(label, onClick) {
  const button = el('button', { type: 'button', class: 'banner-action' }, label);
  button.addEventListener('click', onClick);
  return button;
}

// Aviso de algo desligado, com os botões que resolvem; sem mensagem, some.
function setNotice(id, message, actions = []) {
  const node = $(id);
  node.hidden = !message;
  node.replaceChildren(
    ...(message ? [el('span', {}, message), ...actions.map(([label, onClick]) => actionButton(label, onClick))] : [])
  );
}

function setHiddenToggle(id, shown, total) {
  const button = $(id);
  button.hidden = !total;
  button.setAttribute('aria-pressed', String(shown));
  button.textContent = shown ? 'Esconder ocultas' : `Mostrar ocultas (${total})`;
}

// A cor segue a posição da fonte na lista, usando os tokens de gráfico dos dois temas.
function sourceColor(id) {
  const index = catalog.datasources.findIndex((d) => d.id === id);
  return `var(--chart-${(index % 5) + 1})`;
}

// --- Fonte de dados ----------------------------------------------------------

function base() {
  return `catalog/datasources/${encodeURIComponent(catalog.datasource.id)}`;
}

async function loadDatasources() {
  const data = await attempt(() => api('catalog/datasources'));
  if (!data) return;
  catalog.datasources = data.datasources;
  $('cat-empty').hidden = data.datasources.length > 0;
  if (data.datasources.length) await selectArea(catalog.area ?? data.datasources[0].id);
  else renderSourceTabs();
}

function renderSourceTabs() {
  const tab = (area, label, color, inactive = false) => {
    const button = el('button', {
      type: 'button',
      role: 'tab',
      class: 'source-tab',
      'aria-selected': String(catalog.area === area),
    });
    button.style.setProperty('--source-color', color);
    button.append(label);
    if (inactive) button.append(el('small', {}, 'inativa'));
    button.addEventListener('click', () => selectArea(area));
    return button;
  };
  const sources = catalog.datasources.map((d) => tab(d.id, d.name, sourceColor(d.id), !d.enabled));
  $('cat-source-tabs').replaceChildren(
    ...(sources.length ? [...sources, tab(SHARED_AREA, 'Entre fontes', 'var(--muted)')] : [])
  );
}

async function selectArea(area) {
  if (area !== SHARED_AREA) return selectDatasource(area);
  catalog.area = area;
  $('cat-source-area').hidden = true;
  $('cat-shared-area').hidden = false;
  renderSourceTabs();
  await loadConcepts();
  await refreshLinks();
}

function renderDatasource() {
  const d = catalog.datasource;
  $('cat-source-area').style.setProperty('--source-color', sourceColor(d.id));
  $('cat-source-name').textContent = d.name;
  $('cat-source-id').textContent = d.id;
  $('cat-enabled').checked = d.enabled;
  $('cat-auto-sync').checked = d.auto_sync;
  const synced = d.last_synced_at ? `sincronizada em ${formatDate(d.last_synced_at)}` : 'nunca sincronizada';
  const checked = d.last_checked_at ? `verificada em ${formatDate(d.last_checked_at)}` : 'nunca verificada';
  const queryable = d.entities_queryable === d.entities_visible ? '' : ` · ${d.entities_queryable} consultáveis`;
  $('cat-summary').textContent =
    `${d.entities_visible} de ${d.entities_total} entidades em uso${queryable} · ${synced} · ${checked}`;
  const [label, kind] = SCHEMA_STATUS[d.schema_status] ?? SCHEMA_STATUS.unknown;
  const pill = $('cat-schema-status');
  pill.textContent = label;
  pill.className = `pill ${kind}`.trim();
  setNotice(
    'cat-source-notice',
    d.enabled ? '' : 'Fonte inativa: a Maria não usa este banco, e o schema dele não é verificado.',
    [['Ativar fonte', () => patchDatasource({ enabled: true })]]
  );
  const hint = $('cat-auto-sync-hint');
  hint.hidden = d.auto_sync;
  hint.replaceChildren(
    'Sincronização automática desligada: pode ser ligada para aplicar as mudanças da origem assim que forem detectadas.',
    actionButton('Ligar', () => patchDatasource({ auto_sync: true }))
  );
  renderDrift();
  $('cat-export').href = new URL(`${base()}/export`, API_ROOT);

  const form = $('view-source');
  form.name.value = d.name;
  form.connection_env.value = d.connection_env;
  form.description.value = d.description ?? '';
  form.instructions.value = d.instructions ?? '';
}

async function selectDatasource(id) {
  catalog.area = id;
  renderSourceTabs();
  const datasource = await attempt(() => api(`catalog/datasources/${encodeURIComponent(id)}`));
  if (!datasource || catalog.area !== id) return; // outra aba foi aberta nesse meio-tempo
  if (catalog.datasource?.id !== id) {
    catalog.entity = null;
    catalog.showHidden = false;
    $('cat-search').value = '';
    $('cat-report').hidden = true;
  }
  catalog.datasource = datasource;
  $('cat-shared-area').hidden = true;
  $('cat-source-area').hidden = false;
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

async function patchDatasource(changes, id = catalog.datasource.id) {
  const datasource = await attempt(() =>
    api(`catalog/datasources/${encodeURIComponent(id)}`, { method: 'PATCH', body: JSON.stringify(changes) })
  );
  if (datasource) {
    catalog.datasources = catalog.datasources.map((d) => (d.id === id ? datasource : d));
    renderSourceTabs();
    if (catalog.datasource?.id === id) {
      catalog.datasource = datasource;
      renderDatasource();
    }
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
  const term = $('cat-search').value.trim().toLowerCase();
  if (term) return `${entity.name} ${entity.label ?? ''}`.toLowerCase().includes(term);
  // A entidade aberta fica na lista mesmo depois de ser ocultada.
  return entity.visible || catalog.showHidden || entity.id === catalog.entity?.id;
}

function renderEntityList() {
  setHiddenToggle('cat-toggle-hidden', catalog.showHidden, catalog.entities.filter((e) => !e.visible).length);
  const list = $('cat-entities');
  const items = catalog.entities.filter(entityMatches).map((entity) => {
    const li = el('li', {
      class: [entity.id === catalog.entity?.id && 'active', !entity.visible && 'is-hidden'].filter(Boolean).join(' '),
    });
    const name = el('div', { class: 'entity-name' });
    name.append(el('strong', {}, entity.label ?? entity.name));
    const kind = KIND_LABELS[entity.kind] ?? 'sem sincronizar';
    name.append(el('small', {}, `${entity.name} · ${kind}`));
    li.append(name);
    if (!entity.present) li.append(badge('ausente', 'warn'));
    if (!entity.visible) li.append(badge('oculta'));
    else if (!entity.queryable) li.append(badge('só contexto'));
    li.addEventListener('click', () => selectEntity(entity.id, { show: true }));
    return li;
  });
  const empty = catalog.entities.length
    ? 'Nenhuma entidade encontrada.'
    : 'Nenhuma entidade. Sincronize a fonte.';
  list.replaceChildren(...(items.length ? items : [el('li', { class: 'muted' }, empty)]));
}

async function selectEntity(id, { show = false, revealColumns = false } = {}) {
  const entity = await attempt(() => api(`catalog/entities/${id}`));
  if (!entity) return;
  if (catalog.entity?.id !== id) {
    catalog.showHiddenColumns = false;
    catalog.touchedColumns.clear();
  }
  if (revealColumns) catalog.showHiddenColumns = true;
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
  renderEntityNotice(entity);
  form.label.value = entity.label ?? '';
  form.synonyms.value = entity.synonyms.join(', ');
  renderConceptOptions();
  form.concept_id.value = entity.concept_id ?? '';
  form.description.value = entity.description ?? '';

  const hiddenColumns = entity.columns.filter((c) => !c.visible).length;
  setHiddenToggle('cat-toggle-columns', catalog.showHiddenColumns, hiddenColumns);
  const columns = entity.columns.filter(
    (c) => c.visible || catalog.showHiddenColumns || catalog.touchedColumns.has(c.id)
  );
  const rows = columns.flatMap(renderColumnRows);
  if (!rows.length) {
    const empty = el('tr');
    empty.append(el('td', { colspan: 5, class: 'muted' }, 'Nenhuma coluna visível.'));
    rows.push(empty);
  }
  $('cat-columns').replaceChildren(...rows);
}

function renderEntityNotice(entity) {
  if (!entity.visible) {
    setNotice('cat-entity-notice', 'Entidade oculta: a Maria não a enxerga nem a consulta.', [
      ['Usar nas respostas', () => useEntity(entity.id)],
    ]);
  } else if (!entity.queryable) {
    setNotice('cat-entity-notice', 'Só contexto: a Maria conhece esta entidade, mas não pode consultá-la.', [
      ['Permitir consultas', () => patchEntity(entity.id, { queryable: true })],
    ]);
  } else {
    setNotice('cat-entity-notice', '');
  }
}

const useEntity = (id) => patchEntity(id, { visible: true, queryable: true });

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
    const tr = el('tr', { class: 'column-options-row' });
    const td = el('td', { colspan: 5 });
    td.append(renderColumnOptions(column));
    tr.append(td);
    rows.push(tr);
  }
  return rows;
}

function renderColumnOptions(column) {
  const options = el('div', { class: 'column-options' });

  const access = el('select', { 'aria-label': `Acesso: ${column.name}` });
  access.append(el('option', { value: 'full' }, 'Valores'), el('option', { value: 'aggregate' }, 'Só agregação'));
  access.value = column.access;
  access.addEventListener('change', () => patchColumn(column, { access: access.value }));
  const accessField = el('label', { class: 'field inline' });
  accessField.append(el('span', {}, 'Acesso'), access);

  const searchable = switchInput(column.searchable, (checked) => patchColumn(column, { searchable: checked }), {
    label: `Pesquisável: ${column.name}`,
  });
  searchable.append(el('span', {}, 'Pesquisável'));

  // Se os valores conhecidos entram no contexto do modelo.
  const listing = el('select', { 'aria-label': `Valores no contexto: ${column.name}` });
  listing.append(
    el('option', { value: 'auto' }, 'Automático'),
    el('option', { value: 'always' }, 'Sempre'),
    el('option', { value: 'never' }, 'Nunca')
  );
  listing.value = column.list_values;
  listing.addEventListener('change', () => patchColumn(column, { list_values: listing.value }));
  const listingField = el('label', { class: 'field inline', title: 'Automático: só categorias curtas entram no prompt' });
  listingField.append(el('span', {}, 'Valores no contexto'), listing);

  options.append(accessField, searchable, listingField);
  if (valueRows(column).length) options.append(renderValuesEditor(column));
  return options;
}

// O que foge do padrão aparece mesmo com as opções fechadas.
function columnBadges(column) {
  const badges = [];
  if (column.access === 'aggregate') badges.push(badge('só agregação', 'warn'));
  if (column.searchable) badges.push(badge('pesquisável'));
  if (column.list_values === 'always') badges.push(badge('sempre lista valores'));
  if (column.list_values === 'never') badges.push(badge('nunca lista valores'));
  const pending = column.undescribed_values.length + column.obsolete_values.length;
  if (pending) badges.push(badge(`${pending} a revisar`, 'warn'));
  return badges;
}

function renderColumnRow(column) {
  const tr = el('tr', column.present ? {} : { class: 'is-missing' });
  const name = el('td', { class: 'mono' }, column.name);
  if (column.primary_key) name.append(el('span', { class: 'key', title: 'Chave primária' }, 'PK'));
  if (!column.present) name.append(' ', badge('ausente', 'warn'));
  const badges = columnBadges(column);
  if (badges.length) {
    const row = el('div', { class: 'column-badges' });
    row.append(...badges);
    name.append(row);
  }
  tr.append(name, el('td', { class: 'mono' }, column.data_type ?? '—'));

  const visible = el('td');
  visible.append(
    switchInput(
      column.visible,
      (checked) => {
        catalog.touchedColumns.add(column.id);
        patchColumn(column, { visible: checked });
      },
      { label: `Visível: ${column.name}` }
    )
  );

  const known = valueRows(column).length;
  const toggle = el(
    'button',
    { type: 'button', class: 'ghost', 'aria-expanded': String(catalog.expanded.has(column.id)) },
    known ? `Opções e valores (${known})` : 'Opções'
  );
  toggle.addEventListener('click', () => {
    if (catalog.expanded.has(column.id)) catalog.expanded.delete(column.id);
    else catalog.expanded.add(column.id);
    renderEntity();
  });
  const optionsCell = el('td');
  optionsCell.append(toggle);

  const description = el('input', {
    'aria-label': `Descrição: ${column.name}`,
    placeholder: column.label ?? 'Descreva a coluna…',
  });
  description.value = column.description ?? '';
  description.addEventListener('change', () => patchColumn(column, { description: nullable(description.value) }));
  const descriptionCell = el('td');
  descriptionCell.append(description);

  tr.append(visible, descriptionCell, optionsCell);
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

// --- Ligações entre fontes ----------------------------------------------------

async function loadLinks() {
  const data = await attempt(() => api('catalog/links'));
  if (!data) return;
  renderCrossSourceNotice(data.links);
  const items = data.links.map((link) => {
    const li = el('li');
    const head = el('div', { class: 'concept-head' });
    head.append(
      el('strong', { class: 'mono' }, `${link.from_datasource_id}.${link.from_entity}.${link.from_column}`),
      el('span', {}, '='),
      el('strong', { class: 'mono' }, `${link.to_datasource_id}.${link.to_entity}.${link.to_column}`)
    );
    const actions = el('div', { class: 'actions' });
    actions.append(
      switchInput(link.enabled, (checked) => patchLink(link.id, { enabled: checked }), {
        label: `Ligada: ${link.from_column}`,
      })
    );
    const remove = el('button', { class: 'ghost', type: 'button' }, 'Excluir');
    remove.addEventListener('click', () => deleteLink(link));
    actions.append(remove);
    head.append(actions);
    li.append(head);
    if (link.enabled && !link.active) li.append(renderLinkWarning(link));
    if (link.description) li.append(el('p', { class: 'muted small' }, link.description));
    return li;
  });
  $('cat-links').replaceChildren(...(items.length ? items : [el('li', { class: 'muted' }, 'Nenhuma ligação.')]));
}

function renderLinkWarning(link) {
  const warning = el('div', { class: 'link-warning' });
  warning.append(
    badge('coluna oculta ou ausente: não vale para consultas', 'warn'),
    actionButton(`Abrir ${link.from_entity}`, () => openLinkedEntity(link.from_datasource_id, link.from_entity)),
    actionButton(`Abrir ${link.to_entity}`, () => openLinkedEntity(link.to_datasource_id, link.to_entity))
  );
  return warning;
}

// Mesma condição de chat.py: uma ligação ativa entre duas fontes ativas.
function renderCrossSourceNotice(links) {
  const enabled = new Map(catalog.datasources.map((d) => [d.id, d.enabled]));
  const works = (l) => l.active && enabled.get(l.from_datasource_id) && enabled.get(l.to_datasource_id);
  const prefix = 'Consultas entre fontes indisponíveis:';
  if (links.some(works)) return setNotice('cat-cross-notice', '');
  if (!links.length) {
    return setNotice('cat-cross-notice', `${prefix} não há ligações entre os bancos.`, [
      ['Criar ligação', () => { $('cat-link-details').open = true; $('cat-link-form').source.focus(); }],
    ]);
  }
  const inactive = catalog.datasources.filter(
    (d) => !d.enabled && links.some((l) => [l.from_datasource_id, l.to_datasource_id].includes(d.id))
  );
  if (inactive.length) {
    const names = inactive.map((d) => d.name).join(' e ');
    return setNotice(
      'cat-cross-notice',
      `${prefix} ${names} ${inactive.length > 1 ? 'estão inativas' : 'está inativa'}.`,
      inactive.map((d) => [`Ativar ${d.name}`, () => activateSource(d.id)])
    );
  }
  setNotice(
    'cat-cross-notice',
    links.some((l) => l.enabled)
      ? `${prefix} as ligações têm coluna oculta ou ausente. Abra as entidades na lista de ligações.`
      : `${prefix} as ligações estão desligadas. Ligue uma delas na lista de ligações.`
  );
}

async function activateSource(id) {
  await patchDatasource({ enabled: true }, id);
  await refreshLinks();
}

async function openLinkedEntity(datasourceId, qualifiedName) {
  const data = await attempt(() => api(`catalog/datasources/${encodeURIComponent(datasourceId)}/entities`));
  if (!data) return;
  const entity = data.entities.find((e) => `${e.schema_name}.${e.name}` === qualifiedName);
  if (!entity) return catalogError(`A entidade ${qualifiedName} não está no catálogo.`);
  await selectDatasource(datasourceId);
  await selectEntity(entity.id, { show: true, revealColumns: true });
}

async function refreshLinks() {
  await loadLinks();
  await loadConceptsContext();
}

async function patchLink(id, changes) {
  await attempt(() => api(`catalog/links/${id}`, { method: 'PATCH', body: JSON.stringify(changes) }));
  await refreshLinks();
}

async function deleteLink(link) {
  if (!confirm(`Excluir a ligação ${link.from_column} = ${link.to_column}?`)) return;
  await attempt(() => api(`catalog/links/${link.id}`, { method: 'DELETE' }));
  await refreshLinks();
}

// `fonte:schema.entidade.coluna` nas pontas que a API espera.
function linkEnd(text) {
  const match = text.trim().match(/^([^:\s]+):([^.\s]+)\.([^.\s]+)\.([^.\s]+)$/);
  if (!match) throw new Error(`Use o formato fonte:schema.entidade.coluna em "${text}"`);
  const [, datasource_id, schema_name, entity, column] = match;
  return { datasource_id, schema_name, entity, column };
}

async function createLink(event) {
  event.preventDefault();
  const form = event.target;
  const saved = await attempt(() =>
    api('catalog/links', {
      method: 'POST',
      body: JSON.stringify({
        from: linkEnd(form.source.value),
        to: linkEnd(form.target.value),
        description: nullable(form.description.value),
      }),
    })
  );
  if (!saved) return;
  form.reset();
  flash('cat-link-saved');
  await refreshLinks();
}

function showView(view) {
  catalog.view = view;
  document.querySelectorAll('.subtab').forEach((t) => t.classList.toggle('active', t.dataset.view === view));
  document.querySelectorAll('#tab-catalog .view').forEach((v) => v.classList.toggle('active', v.id === `view-${view}`));
}

async function refreshView() {
  if (catalog.view === 'relationships') await loadRelationships();
  if (catalog.view === 'context') await loadContext();
}

// --- Eventos -----------------------------------------------------------------

document.querySelectorAll('.subtab').forEach((tab) => {
  tab.addEventListener('click', async () => {
    showView(tab.dataset.view);
    await refreshView();
  });
});

$('cat-enabled').addEventListener('change', (event) => patchDatasource({ enabled: event.target.checked }));
$('cat-sync').addEventListener('click', syncDatasource);
$('cat-check').addEventListener('click', checkDatasource);
$('cat-auto-sync').addEventListener('change', (event) => patchDatasource({ auto_sync: event.target.checked }));
$('cat-search').addEventListener('input', renderEntityList);
$('cat-toggle-hidden').addEventListener('click', () => {
  catalog.showHidden = !catalog.showHidden;
  renderEntityList();
});
$('cat-toggle-columns').addEventListener('click', () => {
  catalog.showHiddenColumns = !catalog.showHiddenColumns;
  renderEntity();
});

const entityForm = $('cat-entity-form');
entityForm.visible.addEventListener('change', () =>
  entityForm.visible.checked ? useEntity(catalog.entity.id) : patchEntity(catalog.entity.id, { visible: false })
);
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
$('cat-link-form').addEventListener('submit', createLink);

$('view-source').addEventListener('submit', async (event) => {
  event.preventDefault();
  const form = event.target;
  const saved = await patchDatasource({
    name: form.name.value.trim(),
    connection_env: form.connection_env.value.trim(),
    description: nullable(form.description.value),
    instructions: nullable(form.instructions.value),
  });
  if (saved) flash('cat-source-saved');
});

// Carrega na primeira vez que a aba é aberta.
document.querySelector('.tab[data-tab="catalog"]').addEventListener('click', () => {
  if (!catalog.loaded) {
    catalog.loaded = true;
    loadConcepts().then(loadDatasources);
  }
});
