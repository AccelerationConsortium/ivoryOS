// The shield at the end of a field on the Instruments page: add, change or remove that field's
// safety limit (ivoryos/runtime/safety.py). One editor is open at a time, right under its field.
(function () {
  const grid = document.querySelector('[data-guard-url]');
  if (!grid) return;
  const saveUrl = grid.dataset.guardUrl;
  let open = null;  // {shield, editor}

  function el(tag, props = {}, children = []) {
    const node = document.createElement(tag);
    for (const [key, value] of Object.entries(props)) {
      if (value === undefined || value === null) continue;
      // `list` is read-only as a property; the datalist is named through the attribute
      if (key === 'list' || !(key in node)) node.setAttribute(key, value);
      else node[key] = value;
    }
    for (const child of [].concat(children)) {
      if (child === null || child === undefined) continue;
      node.append(child instanceof Node ? child : document.createTextNode(String(child)));
    }
    return node;
  }

  function close() {
    if (!open) return;
    open.editor.remove();
    open.shield.setAttribute('aria-expanded', 'false');
    open = null;
  }

  function showLimit(shield, limit, hint) {
    const set = Object.keys(limit).length > 0;
    shield.dataset.limit = JSON.stringify(limit);
    shield.classList.toggle('is-set', set);
    shield.title = set ? 'Safety limit: click to change or remove' : 'Add a safety limit';
    shield.replaceChildren(el('i', { className: `bi ${set ? 'bi-shield-check' : 'bi-shield-plus'}` }),
      ...(set ? [el('span', { className: 'ms-1' }, hint)] : []));
  }

  function editorFor(shield) {
    const limit = JSON.parse(shield.dataset.limit || '{}');
    // a number field takes a range and a unit, a text field allowed values, an untyped one either
    const numeric = shield.dataset.kind !== 'text';
    const textual = shield.dataset.kind !== 'number';
    // the inputs have no name, so they are never sent with the method's own form
    const inputs = {};
    const field = (key, label, value, props = {}) => {
      inputs[key] = el('input', { className: 'form-control form-control-sm', value: value ?? '', ...props });
      return el('div', { className: 'col' }, [el('label', { className: 'form-label small text-secondary mb-1' }, label), inputs[key]]);
    };
    const rows = [];
    if (numeric) {
      rows.push(el('div', { className: 'row g-2 mb-2' }, [
        field('min', 'Min', limit.min, { type: 'number', step: 'any' }),
        field('max', 'Max', limit.max, { type: 'number', step: 'any' }),
        field('unit', 'Unit', limit.unit, { list: 'guard-units', placeholder: 'mL' }),
      ]));
    }
    if (textual) {
      rows.push(el('div', { className: 'row g-2 mb-2' }, [
        field('allowed', 'Allowed values', (limit.allowed || []).join(', '), { placeholder: 'Comma-separated; empty for any' }),
      ]));
    }
    const error = el('div', { className: 'small text-danger mb-2 d-none' });
    const save = el('button', { type: 'button', className: 'btn btn-sm btn-primary' }, 'Save');
    const cancel = el('button', { type: 'button', className: 'btn btn-sm btn-outline-secondary' }, 'Cancel');
    const remove = Object.keys(limit).length
      ? el('button', { type: 'button', className: 'btn btn-sm btn-outline-danger me-auto' }, 'Remove') : null;
    const editor = el('div', { className: 'guard-editor border rounded p-2 mb-3 bg-body-tertiary' }, [
      el('div', { className: 'small fw-semibold mb-2' }, `Limit on ${shield.dataset.param}`),
      ...rows, error,
      el('div', { className: 'd-flex gap-2 justify-content-end' }, [remove, cancel, save]),
    ]);

    const collect = () => {
      const typed = {};
      ['min', 'max'].forEach(key => {
        if (inputs[key] && inputs[key].value.trim() !== '') typed[key] = Number(inputs[key].value);
      });
      if (inputs.unit && inputs.unit.value.trim()) typed.unit = inputs.unit.value.trim();
      const allowed = inputs.allowed ? inputs.allowed.value.split(',').map(choice => choice.trim()).filter(Boolean) : [];
      if (allowed.length) typed.allowed = allowed;
      return typed;
    };
    const fail = message => {
      error.textContent = message;
      error.classList.remove('d-none');
    };
    // an empty limit removes the field's limit
    const submit = typed => {
      save.disabled = true;
      fetch(saveUrl, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ method: shield.dataset.method, param: shield.dataset.param, limit: typed }),
      })
        .then(response => response.json().then(data => ({ ok: response.ok, data })))
        .then(({ ok, data }) => {
          if (!ok) {
            // the field is plain from where the message is shown, so drop its `instrument.method.field: `
            const reasons = (data.errors || []).map(e => (e.param ? e.message.replace(/^[^:]*: /, '') : e.message));
            fail(reasons.map(reason => reason.charAt(0).toUpperCase() + reason.slice(1)).join(' ') || 'Not saved.');
            return;
          }
          showLimit(shield, data.limit, data.hint);
          close();
        })
        .catch(() => fail('Not saved: the server did not answer.'))
        .finally(() => { save.disabled = false; });
    };

    save.addEventListener('click', () => submit(collect()));
    cancel.addEventListener('click', close);
    if (remove) remove.addEventListener('click', () => submit({}));
    editor.addEventListener('keydown', event => {
      // Enter saves the limit; left alone it would submit the method's form and run the instrument
      if (event.key === 'Enter') {
        event.preventDefault();
        submit(collect());
      } else if (event.key === 'Escape') {
        close();
      }
    });
    return { editor, first: Object.values(inputs)[0] };
  }

  grid.addEventListener('click', event => {
    const shield = event.target.closest('.guard-shield');
    if (!shield) return;
    event.preventDefault();
    const wasOpen = open && open.shield === shield;
    close();
    if (wasOpen) return;
    const { editor, first } = editorFor(shield);
    shield.closest('.input-group').after(editor);
    shield.setAttribute('aria-expanded', 'true');
    open = { shield, editor };
    if (first) first.focus();
  });
})();
