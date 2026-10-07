// The run panel of the execution page: the optimizer plot, the queue, the form
// for editing a queued task, and the table of the running task while it runs.
// The server's URLs come from the panel's data-urls attribute, set in
// routes/execute/templates/components/logging_panel.html.
const PANEL_URLS = JSON.parse(document.querySelector('.logging-panel').dataset.urls);

async function showPlot() {
    const container = document.getElementById('optimizerPlotsContainer');
    container.innerHTML = '<div class="spinner-border text-primary" role="status"><span class="visually-hidden">Loading...</span></div>';

    try {
        const response = await fetch(PANEL_URLS.optimizerPlot);
        if (!response.ok) {
            container.innerHTML = '<p class="text-danger">No plots found or an error occurred.</p>';
            return;
        }

        // Check content type to see if it's JSON
        const contentType = response.headers.get("content-type");
        if (contentType && contentType.indexOf("application/json") !== -1) {
            const plots = await response.json();

            if (plots.error) {
                container.innerHTML = `<p class="text-danger">${plots.error}</p>`;
                return;
            }

            container.innerHTML = ''; // clear loading

            for (const [plotName, htmlSnippet] of Object.entries(plots)) {
                const plotWrapper = document.createElement('div');
                plotWrapper.className = "card mb-3";

                const cardHeader = document.createElement('div');
                cardHeader.className = "card-header fw-bold";
                cardHeader.innerText = plotName;

                const cardBody = document.createElement('div');
                cardBody.className = "card-body overflow-auto d-flex";
                // Ax figures have fixed widths. Plain centering would push a figure wider
                // than the card past its left edge, where it can't be scrolled to;
                // "safe" left-aligns it instead (older browsers ignore this and left-align).
                cardBody.style.justifyContent = "safe center";

                // innerHTML doesn't run the snippet's <script>, see below
                cardBody.innerHTML = htmlSnippet;

                plotWrapper.appendChild(cardHeader);
                plotWrapper.appendChild(cardBody);
                container.appendChild(plotWrapper);

                // Force script execution
                Array.from(cardBody.querySelectorAll("script")).forEach(oldScript => {
                    const newScript = document.createElement("script");
                    Array.from(oldScript.attributes).forEach(attr => newScript.setAttribute(attr.name, attr.value));
                    newScript.appendChild(document.createTextNode(oldScript.innerHTML));
                    oldScript.parentNode.replaceChild(newScript, oldScript);
                });
            }
        } else {
            // Fallback for returning an image (e.g. from NIMO optimizer)
            const blob = await response.blob();
            const url = URL.createObjectURL(blob);
            container.innerHTML = `<img src="${url}" class="img-fluid rounded shadow-sm d-block mx-auto" style="max-width:100%;">`;
        }
    } catch (error) {
        container.innerHTML = `<p class="text-danger">Error fetching plot: ${error.message}</p>`;
    }
}

// Read-only details of the running task. Queued tasks open in the edit form instead.
function renderTaskDetails(details, fullConfig = null) {
  const content = document.getElementById('queue-details-content');
  content.innerHTML = '';

  if (!details) {
    content.innerText = "No details available.";
    return;
  }

  const table = document.createElement('table');
  table.className = 'table table-striped table-sm';
  const tbody = document.createElement('tbody');

  for (const [key, value] of Object.entries(details)) {
    if (key === 'Full Config') continue;

    const row = document.createElement('tr');
    const th = document.createElement('th');
    th.scope = 'row';
    th.innerText = key;
    const td = document.createElement('td');

    if (typeof value === 'object' && value !== null) {
      td.innerHTML = `<pre class="m-0" style="max-height: 200px; overflow: auto;">${JSON.stringify(value, null, 2)}</pre>`;
    } else {
      td.innerText = value;
    }
    row.appendChild(th);
    row.appendChild(td);
    tbody.appendChild(row);
  }
  table.appendChild(tbody);
  content.appendChild(table);

  if (fullConfig) {
    const configContainer = document.createElement('div');
    configContainer.className = 'mt-3';
    configContainer.innerHTML = `<h6>Full Configuration (${fullConfig.length} entries):</h6>`;
    const pre = document.createElement('pre');
    pre.className = 'bg-white p-2 border rounded';
    pre.style.maxHeight = '400px';
    pre.style.overflow = 'auto';
    pre.innerText = JSON.stringify(fullConfig, null, 2);
    configContainer.appendChild(pre);
    content.appendChild(configContainer);
  }
}

function renderQueue(data) {
  const queueList = document.getElementById('queue-list');
  if (!queueList) return;

  queueList.innerHTML = '';
  if (data.length === 0) {
    queueList.innerHTML = '<div class="list-group-item text-center text-muted">No pending tasks</div>';
    return;
  }
  data.forEach((task, index) => {
    const item = document.createElement('div');
    item.className = 'list-group-item d-flex justify-content-between align-items-center';

    const infoDiv = document.createElement('div');
    infoDiv.style.cursor = 'pointer';
    infoDiv.setAttribute('title', 'Click to edit');

    let batchBadge = '';
    if (task.details && task.details['Batch Size']) {
      batchBadge = `<span class="badge bg-info text-dark ms-2">Batch: ${task.details['Batch Size']}</span>`;
    }

    infoDiv.innerHTML = `
        <span class="badge bg-secondary me-2">#${index + 1}</span>
        <span class="fw-bold">${task.name}</span>
        ${batchBadge}
        <br>
        <small class="text-muted ms-4">${task.args}</small>
    `;
    infoDiv.onclick = () => openQueuedTask(task.uid);
    item.appendChild(infoDiv);

    const controlsDiv = document.createElement('div');
    controlsDiv.innerHTML = `
        <button class="btn btn-sm btn-outline-primary" title="Edit" onclick="openQueuedTask('${task.uid}')">
          <i class="bi bi-pencil"></i>
        </button>
        <button class="btn btn-sm btn-outline-secondary" onclick="reorderTask(${index}, 'up')" ${index === 0 ? 'disabled' : ''}>
          <i class="bi bi-arrow-up"></i>
        </button>
        <button class="btn btn-sm btn-outline-secondary" onclick="reorderTask(${index}, 'down')" ${index === data.length - 1 ? 'disabled' : ''}>
          <i class="bi bi-arrow-down"></i>
        </button>
        <button class="btn btn-sm btn-outline-danger" onclick="deleteTask(${index})">
          <i class="bi bi-trash"></i>
        </button>
    `;
    item.appendChild(controlsDiv);
    queueList.appendChild(item);
  });
}

function updateQueue() {
  // Initial fetch or manual refresh
  const timestamp = new Date().getTime();
  fetch(PANEL_URLS.queue + "?t=" + timestamp)
    .then(response => response.json())
    .then(data => renderQueue(data))
    .catch(error => console.error('Error fetching queue:', error));
}

function deleteTask(id) {
  fetch(PANEL_URLS.queueDelete, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({ id: id })
  })
    .then(response => response.json())
    .then(data => {
      if (data.status !== 'ok') {
        console.error('Delete failed:', data.error);
      }
    })
    .catch(error => console.error('Error deleting task:', error));
}

function reorderTask(id, direction) {
  fetch(PANEL_URLS.queueReorder, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({ id: id, direction: direction })
  })
    .then(response => response.json())
    .then(data => {
      if (data.status !== 'ok') {
        console.error('Reorder failed:', data.error);
      }
    })
    .catch(error => console.error('Error reordering task:', error));
}

// ---- Editing a queued task ----
// A queued task keeps its name, repeat count, config entries or optimization
// settings untouched until it starts, so they can all still be changed.
let currentTaskUid = null;
let editedConditions = null;
// the running task's config table, while its live editor is open
let liveTable = null;
let liveRefresh = null;
const LIVE_CONFIG_URL = PANEL_URLS.runningConfig;

function conditionsUrl(uid) {
  return PANEL_URLS.taskConditions.replace('__uid__', encodeURIComponent(uid));
}

function el(tag, props = {}, children = []) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(props)) {
    if (value === undefined || value === null) continue;
    if (key === 'dataset') Object.assign(node.dataset, value);
    else if (key === 'style') node.setAttribute('style', value);
    else if (key in node) node[key] = value;
    else node.setAttribute(key, value);
  }
  for (const child of [].concat(children)) {
    if (child === null || child === undefined || child === false) continue;
    node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return node;
}

function showConditionsError(message, tone = 'danger') {
  const box = document.getElementById('conditions-error');
  box.className = `alert alert-${tone} py-2`;
  box.style.whiteSpace = 'pre-line';
  box.textContent = message || '';
  box.classList.toggle('d-none', !message);
}

// The modal shows either the edit form of a queued task or the read-only
// details of the running one.
function showTaskModal(view, title) {
  const editing = view === 'form';
  document.getElementById('queue-details-content').classList.toggle('d-none', editing);
  document.getElementById('conditions-editor').classList.toggle('d-none', !editing);
  document.getElementById('cancel-conditions-btn').classList.toggle('d-none', !editing);
  document.getElementById('save-conditions-btn').classList.toggle('d-none', !editing || !(editedConditions || liveTable));
  document.getElementById('close-details-btn').classList.toggle('d-none', editing);
  document.querySelector('#queueDetailsModal .modal-title').innerText = title;
  bootstrap.Modal.getOrCreateInstance(document.getElementById('queueDetailsModal')).show();
}

function openQueuedTask(uid) {
  currentTaskUid = uid;
  editedConditions = null;
  showConditionsError('');
  const editor = document.getElementById('conditions-editor');
  fetch(conditionsUrl(uid))
    .then(response => response.json().then(data => ({ ok: response.ok, data })))
    .then(({ ok, data }) => {
      if (!ok) throw new Error(data.error || 'Could not load this task.');
      editedConditions = data;
      editor.replaceChildren(...buildConditionsEditor(data));
    })
    .catch(error => {
      editor.replaceChildren();
      showConditionsError(error.message);
    })
    .finally(() => showTaskModal('form', 'Queued Task'));
}

function resetTaskModal() {
  currentTaskUid = null;
  editedConditions = null;
  liveTable = null;
  clearInterval(liveRefresh);
  liveRefresh = null;
  showConditionsError('');
}

function saveConditions() {
  if (liveTable) return saveRunningConfig();
  if (!currentTaskUid || !editedConditions) return;
  const saveButton = document.getElementById('save-conditions-btn');
  saveButton.disabled = true;
  showConditionsError('');
  fetch(conditionsUrl(currentTaskUid), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(collectConditions()),
  })
    .then(response => response.json().then(data => ({ ok: response.ok, data })))
    .then(({ ok, data }) => {
      if (!ok) throw new Error(data.error || 'Could not save this task.');
      bootstrap.Modal.getOrCreateInstance(document.getElementById('queueDetailsModal')).hide();
      updateQueue();
    })
    .catch(error => showConditionsError(error.message))
    .finally(() => { saveButton.disabled = false; });
}

function editorSection(title, children) {
  return el('div', { className: 'mb-4' }, [
    el('h6', { className: 'fw-bold border-bottom pb-2 mb-3 text-secondary' }, title),
    ...[].concat(children),
  ]);
}

function editorNumber(id, label, value) {
  return el('div', { className: 'col-sm-4' }, [
    el('label', { className: 'form-label small fw-bold mb-1', htmlFor: id }, label),
    el('input', { type: 'number', className: 'form-control form-control-sm', id, min: '1', step: '1', value: value ?? '' }),
  ]);
}

const MODE_LABELS = { repeat: 'Repeated execution', config: 'Configuration list', optimizer: 'Bayesian optimization' };

function buildConditionsEditor(c) {
  const runFields = [
    el('div', { className: 'col-12' }, [
      el('label', { className: 'form-label small fw-bold mb-1', htmlFor: 'cond-name' }, 'Experiment name'),
      el('input', { type: 'text', className: 'form-control form-control-sm', id: 'cond-name', value: c.name ?? '' }),
    ]),
  ];
  if (c.mode !== 'config') {
    runFields.push(editorNumber('cond-repeat-count', c.mode === 'optimizer' ? 'Iterations' : 'Repeat count', c.repeat_count));
  }
  runFields.push(editorNumber('cond-batch-size', 'Batch size', c.batch_size));
  if (c.history) {
    runFields.push(el('div', { className: 'col-12 small text-muted' }, ['Existing data: ', el('span', { className: 'font-monospace' }, c.history)]));
  }
  const mode = [MODE_LABELS[c.mode], c.optimizer].filter(Boolean).join(' · ');
  const parts = [editorSection(`Run · ${mode}`, el('div', { className: 'row g-2' }, runFields))];
  if (c.mode === 'config') parts.push(editorSection('Config entries', configEditor(c)));
  if (c.mode === 'optimizer') parts.push(...optimizerEditor(c));
  return parts;
}

// `live` is the running task's table, whose rows carry an id and a status
function configEditor(c, live = false) {
  const body = el('tbody', { id: 'cond-config-rows' });
  c.rows.forEach(row => body.append(live ? configRow(c.fields, row.values, row) : configRow(c.fields, row)));
  renumberConfigRows(body);
  const header = el('tr', {}, [
    el('th', { className: 'small text-muted', style: 'width: 2.5em' }, '#'),
    live ? el('th', { className: 'small text-muted', style: 'width: 6em' }, 'Status') : null,
    ...c.fields.map(field => el('th', { className: 'small text-nowrap' }, [
      field,
      c.types[field] ? el('span', { className: 'text-muted fw-normal ms-1' }, `(${c.types[field]})`) : null,
    ])),
    el('th', { style: 'width: 2.5em' }),
  ]);
  // only the entries scroll, header row in view, so what sits above and the
  // add button below stay put however long the table is
  const scroller = el('div', { id: 'cond-config-scroll', className: 'table-responsive border rounded mb-2', style: 'max-height: 50vh; overflow-y: auto;' },
    el('table', { className: 'table table-sm table-bordered align-middle mb-0' }, [
      el('thead', { className: 'table-light sticky-top' }, header),
      body,
    ]));
  const addButton = el('button', {
    type: 'button', className: 'btn btn-sm btn-outline-secondary',
    onclick: () => {
      const row = configRow(c.fields, [], live ? { id: null, status: 'new' } : undefined);
      body.append(row);
      renumberConfigRows(body);
      scroller.scrollTop = scroller.scrollHeight;
      row.querySelector('input').focus();
    },
  }, [el('i', { className: 'bi bi-plus-lg me-1' }), 'Add entry']);
  return [scroller, addButton];
}

// `meta` ({id, status, reason}) is given for a row of the running task's table
function configRow(fields, values, meta) {
  const row = el('tr');
  row.append(
    el('td', { className: 'small text-muted row-number' }),
    meta ? el('td', { className: 'p-1' }, el('span', { className: 'badge row-status' })) : null,
    ...fields.map((field, i) => el('td', { className: 'p-1' },
      el('input', {
        type: 'text', className: 'form-control form-control-sm', value: values[i] ?? '', dataset: { field },
        // being fixed, so no longer marked as a value that cannot run
        oninput: event => { event.target.classList.remove('is-invalid'); event.target.removeAttribute('title'); },
      }))),
    el('td', { className: 'p-1 text-center' },
      el('button', {
        type: 'button', className: 'btn btn-sm btn-outline-danger row-remove', title: 'Remove this entry',
        onclick: () => { const body = row.parentNode; row.remove(); renumberConfigRows(body); },
      }, el('i', { className: 'bi bi-x-lg' }))),
  );
  if (meta) {
    if (meta.id != null) row.dataset.id = meta.id;
    setRowStatus(row, meta);
  }
  return row;
}

const ROW_STATUS = {
  done: { label: 'done', badge: 'text-bg-success', row: 'table-light' },
  stopped: { label: 'stopped', badge: 'text-bg-warning', row: 'table-light' },
  failed: { label: 'failed', badge: 'text-bg-danger', row: 'table-light' },
  running: { label: 'running', badge: 'text-bg-primary', row: 'table-primary' },
  pending: { label: 'pending', badge: 'text-bg-secondary', row: '' },
  new: { label: 'new', badge: 'text-bg-info', row: '' },
};

const isFinished = status => ['done', 'stopped', 'failed'].includes(status);

// Rows that ran are locked; the running row can be edited but not removed.
function setRowStatus(row, meta) {
  const look = ROW_STATUS[meta.status] || ROW_STATUS.pending;
  row.className = look.row;
  row.dataset.status = meta.status;
  row.querySelectorAll('input').forEach(input => { input.disabled = isFinished(meta.status); });
  const badge = row.querySelector('.row-status');
  badge.className = `badge row-status ${look.badge}`;
  badge.textContent = look.label;
  badge.title = meta.reason || '';
  // a value that cannot run is outlined in red, the reason on hover
  const invalid = meta.invalid || {};
  row.querySelectorAll('input[data-field]').forEach(input => {
    const reason = invalid[input.dataset.field];
    input.classList.toggle('is-invalid', Boolean(reason));
    if (reason) input.title = reason; else input.removeAttribute('title');
  });
  row.querySelector('.row-remove').classList.toggle('invisible', isFinished(meta.status) || meta.status === 'running');
}

function renumberConfigRows(body) {
  body.querySelectorAll('.row-number').forEach((cell, i) => { cell.textContent = i + 1; });
}

// ---- Editing the running task's config table ----
// The run takes rows one batch at a time, so rows it has not reached can be
// edited, added or removed, and the running row's changes reach its remaining
// steps. The table refreshes its row statuses while it is open.

function fetchRunningConfig() {
  return fetch(LIVE_CONFIG_URL + '?t=' + Date.now())
    .then(response => response.json().then(data => ({ ok: response.ok, data })));
}

// Resolves to whether the running task has a config table to show.
function openRunningConfig() {
  return fetchRunningConfig().then(({ ok, data }) => {
    if (!ok) return false;
    resetTaskModal();
    liveTable = data;
    document.getElementById('conditions-editor').replaceChildren(
      editorSection(`Progress · ${data.name}`, el('div', { id: 'live-progress' }, liveProgress(data.counts))),
      editorSection('Config entries', configEditor(data, true)),
    );
    // the table scrolls on its own, so bring the row in progress into view
    const modal = document.getElementById('queueDetailsModal');
    if (modal.classList.contains('show')) scrollToRunningRow();
    else modal.addEventListener('shown.bs.modal', scrollToRunningRow, { once: true });
    showTaskModal('form', 'Current Run');
    liveRefresh = setInterval(refreshRunningConfig, 2000);
    return true;
  }).catch(() => false);
}

function scrollToRunningRow() {
  const running = document.querySelector('#cond-config-rows tr[data-status="running"]');
  const scroller = document.getElementById('cond-config-scroll');
  if (running && scroller) scroller.scrollTop = Math.max(0, running.offsetTop - scroller.clientHeight / 3);
}

function liveProgress(counts) {
  const total = Object.values(counts).reduce((sum, n) => sum + n, 0);
  const unfinished = (counts.failed || 0) + (counts.stopped || 0);
  const share = n => `${total ? (n * 100) / total : 0}%`;
  const segment = (n, bar) => el('div', { className: 'progress', role: 'progressbar', style: `width: ${share(n)}` },
    el('div', { className: `progress-bar ${bar}` }));
  const summary = [`${counts.done} of ${total} rows done`];
  if (counts.failed) summary.push(`${counts.failed} failed`);
  if (counts.running) summary.push(`${counts.running} running`);
  return [
    el('div', { className: 'small text-muted mb-1' }, summary.join(' · ')),
    el('div', { className: 'progress-stacked', style: 'height: 10px' }, [
      segment(counts.done, 'bg-success'),
      segment(unfinished, 'bg-danger'),
      segment(counts.running, 'progress-bar-striped progress-bar-animated'),
    ]),
  ];
}

// Updates row statuses and progress without touching what is being typed,
// except in rows that just finished: they show the values they ran with.
function refreshRunningConfig() {
  if (!liveTable) return;
  fetchRunningConfig().then(({ ok, data }) => {
    if (!liveTable) return;
    if (!ok || data.uid !== liveTable.uid) {
      clearInterval(liveRefresh);
      liveRefresh = null;
      liveTable = null;
      document.getElementById('save-conditions-btn').classList.add('d-none');
      document.querySelectorAll('#cond-config-rows input, #cond-config-rows button, #conditions-editor > div > button')
        .forEach(control => { control.disabled = true; });
      showConditionsError('The run has finished, so its table can no longer be edited.', 'info');
      return;
    }
    document.getElementById('live-progress').replaceChildren(...liveProgress(data.counts));
    const lost = [];
    data.rows.forEach(server => {
      const row = document.querySelector(`#cond-config-rows tr[data-id="${server.id}"]`);
      if (!row || row.dataset.status === server.status) return;
      if (isFinished(server.status)) {
        const inputs = row.querySelectorAll('input[data-field]');
        if ([...inputs].some((input, i) => input.value !== (server.values[i] ?? ''))) lost.push(row.querySelector('.row-number').textContent);
        inputs.forEach((input, i) => { input.value = server.values[i] ?? ''; });
      }
      setRowStatus(row, server);
    });
    if (lost.length) {
      showConditionsError(`Row ${lost.join(', ')} finished before your changes were saved, so it ran as it was.`, 'warning');
    }
  }).catch(() => {});
}

function collectLiveRows() {
  return [...document.querySelectorAll('#cond-config-rows tr')]
    .map((row, i) => ({ row, number: i + 1 }))
    .filter(({ row }) => !isFinished(row.dataset.status))
    .map(({ row, number }) => {
      const values = {};
      row.querySelectorAll('input[data-field]').forEach(input => { values[input.dataset.field] = input.value; });
      return { id: row.dataset.id ? Number(row.dataset.id) : null, values, number };
    });
}

function saveRunningConfig() {
  const saveButton = document.getElementById('save-conditions-btn');
  saveButton.disabled = true;
  showConditionsError('');
  fetch(LIVE_CONFIG_URL, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ uid: liveTable.uid, rows: collectLiveRows() }),
  })
    .then(response => response.json().then(data => ({ ok: response.ok, data })))
    .then(({ ok, data }) => {
      if (!ok) throw new Error(data.error || 'Could not save the table.');
      if (!data.notes || !data.notes.length) {
        bootstrap.Modal.getOrCreateInstance(document.getElementById('queueDetailsModal')).hide();
        return;
      }
      // the rest was saved; show the table as it is now, with what was not applied
      return openRunningConfig().then(() => showConditionsError(`Saved, except:\n${data.notes.join('\n')}`, 'warning'));
    })
    .catch(error => showConditionsError(error.message))
    .finally(() => { saveButton.disabled = false; });
}

function optimizerEditor(c) {
  const parts = [
    editorSection('Parameters', el('table', { className: 'table table-sm align-middle mb-0' },
      el('tbody', { id: 'cond-parameters' }, c.parameters.map(p => parameterRow(p, c.requires_step))))),
    editorSection('Objectives', el('table', { className: 'table table-sm align-middle mb-0' },
      el('tbody', { id: 'cond-objectives' }, c.objectives.map(objectiveRow)))),
  ];
  if (c.supports_constraints || c.constraints.length) {
    const list = el('div', { id: 'cond-constraints' }, c.constraints.map(constraintRow));
    parts.push(editorSection('Constraints', [list,
      el('button', { type: 'button', className: 'btn btn-sm btn-outline-secondary', onclick: () => list.append(constraintRow('')) },
        [el('i', { className: 'bi bi-plus-lg me-1' }), 'Add constraint'])]));
  }
  if (c.steps.length) {
    parts.push(editorSection('Model configuration', el('div', { className: 'row g-2' }, c.steps.map(stepCard))));
  }
  if (c.additional_params.length) {
    parts.push(editorSection('Advanced', el('div', { className: 'row g-2', id: 'cond-additional' }, c.additional_params.map(additionalField))));
  }
  return parts;
}

function parameterRow(p, requiresStep) {
  const input = (role, placeholder, value) =>
    el('input', { type: 'text', className: 'form-control form-control-sm', placeholder, value, dataset: { role } });
  const type = el('select', { className: 'form-select form-select-sm', dataset: { role: 'type' } },
    p.types.map(t => el('option', { value: t, selected: t === p.type }, t)));
  const range = el('div', { className: 'input-group input-group-sm', dataset: { kind: 'range' } }, [
    input('min', 'Min', p.min),
    input('max', 'Max', p.max),
    input('step', requiresStep ? 'Step (required)' : 'Step (optional)', p.step),
  ]);
  const choices = el('div', { dataset: { kind: 'choice' } }, input('choices', 'Choices, comma separated', p.choices));
  const fixed = el('div', { dataset: { kind: 'fixed' } }, input('value', 'Fixed value', p.value));
  const showInputs = () => {
    const kind = type.value === 'substance' ? 'choice' : type.value;
    [range, choices, fixed].forEach(node => node.classList.toggle('d-none', node.dataset.kind !== kind));
  };
  type.addEventListener('change', showInputs);
  showInputs();
  return el('tr', { dataset: { name: p.name } }, [
    el('td', { className: 'small fw-medium' }, [p.name, el('span', { className: 'text-muted fw-normal ms-1' }, `(${p.value_type})`)]),
    el('td', { style: 'width: 9em' }, type),
    el('td', {}, [range, choices, fixed]),
  ]);
}

function objectiveRow(o) {
  return el('tr', { dataset: { name: o.name } }, [
    el('td', { className: 'small fw-medium' }, o.name),
    el('td', { style: 'width: 9em' }, el('select', { className: 'form-select form-select-sm', dataset: { role: 'goal' } },
      ['minimize', 'maximize', 'none'].map(goal => el('option', { value: goal, selected: goal === o.goal }, goal)))),
    el('td', {}, el('input', {
      type: 'number', step: 'any', className: 'form-control form-control-sm',
      placeholder: 'Early stop threshold (optional)', value: o.early_stop, dataset: { role: 'early_stop' },
    })),
  ]);
}

function constraintRow(expression) {
  const row = el('div', { className: 'input-group input-group-sm mb-2' });
  row.append(
    el('input', { type: 'text', className: 'form-control', placeholder: 'e.g. a + b <= 80', value: expression }),
    el('button', { type: 'button', className: 'btn btn-outline-danger', title: 'Remove this constraint', onclick: () => row.remove() },
      el('i', { className: 'bi bi-x-lg' })),
  );
  return row;
}

function stepCard(step) {
  const fields = [
    el('label', { className: 'form-label small fw-bold mb-1' }, 'Model'),
    el('select', { className: 'form-select form-select-sm mb-2', dataset: { role: 'model' } }, [
      step.model ? null : el('option', { value: '', selected: true }, '-- Default --'),
      ...step.models.map(model => el('option', { value: model, selected: model === step.model }, model)),
    ]),
  ];
  if (step.has_num_samples) {
    fields.push(
      el('label', { className: 'form-label small fw-bold mb-1' }, 'Num samples'),
      el('input', { type: 'number', min: '0', step: '1', className: 'form-control form-control-sm', value: step.num_samples, dataset: { role: 'num_samples' } }),
    );
  }
  return el('div', { className: 'col-md-6' }, el('div', { className: 'card bg-light border h-100', dataset: { step: step.key } }, [
    el('div', { className: 'card-header py-1 bg-white' }, el('small', { className: 'fw-bold text-muted' }, step.label)),
    el('div', { className: 'card-body py-2' }, fields),
  ]));
}

function additionalField(field) {
  const isList = field.type.startsWith('list');
  let input;
  if (field.type === 'choice' && field.options.length) {
    input = el('select', { className: 'form-select form-select-sm' }, [
      el('option', { value: '', selected: !field.value }, 'Default'),
      ...field.options.map(option => el('option', { value: String(option), selected: String(option) === field.value }, String(option))),
    ]);
  } else {
    const isNumber = field.type === 'int' || field.type === 'float';
    input = el('input', {
      type: isNumber ? 'number' : 'text', step: isNumber ? (field.type === 'float' ? 'any' : '1') : undefined,
      className: 'form-control form-control-sm', placeholder: isList ? 'e.g. 1, 2, 3' : 'Optional', value: field.value,
    });
  }
  input.dataset.name = field.name;
  return el('div', { className: 'col-md-6' }, [
    el('label', { className: 'form-label small fw-bold mb-1' }, isList ? `${field.name} (comma-separated)` : field.name),
    input,
  ]);
}

function collectConditions() {
  const c = editedConditions;
  const editor = document.getElementById('conditions-editor');
  const payload = {
    name: editor.querySelector('#cond-name').value,
    batch_size: editor.querySelector('#cond-batch-size').value,
  };
  if (c.mode !== 'config') payload.repeat_count = editor.querySelector('#cond-repeat-count').value;
  if (c.mode === 'config') {
    payload.config = [...editor.querySelectorAll('#cond-config-rows tr')].map(row => {
      const entry = {};
      row.querySelectorAll('input[data-field]').forEach(input => { entry[input.dataset.field] = input.value; });
      return entry;
    });
  }
  if (c.mode === 'optimizer') {
    payload.parameters = [...editor.querySelectorAll('#cond-parameters tr')].map(row => {
      const value = role => row.querySelector(`[data-role="${role}"]`).value;
      return {
        name: row.dataset.name, type: value('type'),
        min: value('min'), max: value('max'), step: value('step'), choices: value('choices'), value: value('value'),
      };
    });
    payload.objectives = [...editor.querySelectorAll('#cond-objectives tr')].map(row => ({
      name: row.dataset.name,
      goal: row.querySelector('[data-role="goal"]').value,
      early_stop: row.querySelector('[data-role="early_stop"]').value,
    }));
    const constraints = editor.querySelector('#cond-constraints');
    if (constraints) payload.constraints = [...constraints.querySelectorAll('input')].map(input => input.value);
    const steps = editor.querySelectorAll('[data-step]');
    if (steps.length) {
      payload.steps = {};
      steps.forEach(card => {
        const entry = { model: card.querySelector('[data-role="model"]').value };
        const samples = card.querySelector('[data-role="num_samples"]');
        if (samples) entry.num_samples = samples.value;
        payload.steps[card.dataset.step] = entry;
      });
    }
    const additional = editor.querySelectorAll('#cond-additional [data-name]');
    if (additional.length) {
      payload.additional_params = {};
      additional.forEach(input => { payload.additional_params[input.dataset.name] = input.value; });
    }
  }
  return payload;
}

document.getElementById('queueDetailsModal').addEventListener('hidden.bs.modal', resetTaskModal);

// Listen for queue updates via WebSocket
document.addEventListener('DOMContentLoaded', () => {
  const checkSocket = setInterval(() => {
      if (window.socket) {
          clearInterval(checkSocket);
          window.socket.on('queue_status', (data) => {
              console.log("Queue status update received via socket");
              renderQueue(data);
          });
      }
  }, 100);
});
updateQueue(); // Initial call

// Current Run Configuration Logic: a config table run opens as an editable
// table; anything else shows its details read-only
document.getElementById('view-current-config').addEventListener('click', function() {
  openRunningConfig().then(opened => { if (!opened) showCurrentRunDetails(); });
});

function showCurrentRunDetails() {
  fetch(PANEL_URLS.currentTask)
    .then(response => {
        if (!response.ok) {
            return response.json().then(data => { throw new Error(data.error || "Failed to fetch current config"); });
        }
        return response.json();
    })
    .then(data => {
        if (data.error) {
            showRunMessage('Nothing is running right now.');
            return;
        }
        resetTaskModal();
        renderTaskDetails(data, data["Full Config"] || null);
        showTaskModal('details', 'Current Run Details');
    })
    .catch(error => {
        showRunMessage(`Could not load the current run: ${error.message}`, 'danger');
    });
}

// A short message in the same modal the info button opens, rather than a browser alert.
function showRunMessage(message, tone = 'secondary') {
  resetTaskModal();
  showTaskModal('details', 'Current Run');
  document.getElementById('queue-details-content').classList.add('d-none');
  showConditionsError(message, tone);
}

// The info button is also the way into the running table's editor, so while
// there is a table to edit it shows a pencil and says so.
function setInfoButtonEditable(editable) {
  const button = document.getElementById('view-current-config');
  button.querySelector('i').className = editable ? 'bi bi-pencil-square' : 'bi bi-info-circle';
  button.title = editable ? "View or edit the current run's table" : 'View current run';
  button.classList.toggle('text-primary', editable);
  button.classList.toggle('text-secondary', !editable);
}

fetchRunningConfig().then(({ ok }) => setInfoButtonEditable(ok)).catch(() => {});
document.addEventListener('DOMContentLoaded', () => {
  const waitForSocket = setInterval(() => {
    if (!window.socket) return;
    clearInterval(waitForSocket);
    window.socket.on('live_config', data => setInfoButtonEditable(Boolean(data.editable)));
  }, 100);
});
