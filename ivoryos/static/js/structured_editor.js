// Dict arguments (``settings: dict``, ``Dict[str, float]``) come as a <textarea> of JSON with a data-schema
// attribute that describes their keys and values (StructuredField in forms/dynamic_forms.py). This shows that
// JSON as a table of keys and values instead. Every edit rewrites the textarea, which is what the form
// submits, so the server still parses and validates the value; "JSON" shows the textarea itself.
(function () {
    "use strict";

    const VARIABLE = /^#[A-Za-z_]\w*$/;
    const NUMBER = /^[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?$/;
    const PYTHON_CONSTANTS = new Map([["None", null], ["True", true], ["False", false]]);

    // textarea -> editor. Never an attribute: forms are copied as HTML (a toolbox action dragged onto the
    // canvas), and the copy needs an editor of its own
    const editors = new WeakMap();
    let lastId = 0;

    // Text the inputs can't turn into a value, such as a misspelled number: written into the JSON as typed,
    // so the server parses or reports it when the form is submitted
    class RawText {
        constructor(text) {
            this.text = text;
        }
    }

    // ------------------------------------------------------------------------
    // values
    // ------------------------------------------------------------------------

    function isObject(value) {
        return value !== null && typeof value === "object" && !Array.isArray(value) && !(value instanceof RawText);
    }

    function isNumberField(schema) {
        return schema.kind === "scalar" && (schema.type === "int" || schema.type === "float");
    }

    // The value of a new entry: zero / empty for a typed value, None otherwise
    function templateFor(schema) {
        if (schema.optional) return null;
        if (schema.kind === "dict") return {};
        if (schema.kind === "enum") return schema.choices.length ? schema.choices[0] : null;
        if (schema.kind === "scalar") return { bool: false, int: 0, float: 0, str: "" }[schema.type];
        return null;
    }

    // JSON text, indented like the server's json.dumps(indent=2). A whole number in a float value keeps its
    // ".0", so it is stored as a float.
    function serialize(value, schema, indent) {
        indent = indent || "";
        const inner = indent + "  ";
        if (value instanceof RawText) return value.text;
        if (Array.isArray(value)) {
            if (!value.length) return "[]";
            return "[\n" + value.map(v => inner + serialize(v, null, inner)).join(",\n") + "\n" + indent + "]";
        }
        if (isObject(value)) {
            const isDict = !!schema && schema.kind === "dict";
            const keys = Object.keys(value);
            if (!keys.length) return "{}";
            // number keys of a dict[int, ...] stay unquoted, so the server reads numbers
            const keyText = key => (isDict && isNumberField(schema.key) && NUMBER.test(key) ? key : JSON.stringify(key));
            return "{\n" + keys.map(key => inner + keyText(key) + ": " +
                serialize(value[key], isDict ? schema.value : null, inner)).join(",\n") + "\n" + indent + "}";
        }
        if (typeof value === "number" && schema && schema.type === "float" && /^-?\d+$/.test(String(value))) {
            return value + ".0";
        }
        return JSON.stringify(value);
    }

    // JSON text as a value, also with the unquoted number keys serialize() writes for a dict[int, ...]
    function readJson(text) {
        try {
            return JSON.parse(text);
        } catch (e) {
            return JSON.parse(text.replace(/([{,]\s*)(-?\d+(?:\.\d+)?)(\s*:)/g, '$1"$2"$3'));
        }
    }

    // What an input shows for a value
    function display(value, schema) {
        if (value === null || value === undefined) return "";
        if (value instanceof RawText) return value.text;
        if (typeof value === "string") {
            // a free-form value quotes text only where it would read back as something else, e.g. "5"
            if (schema.kind !== "json" || VARIABLE.test(value)) return value;
            return parseLoose(value) === value ? value : JSON.stringify(value);
        }
        if (typeof value === "object") return JSON.stringify(value);
        return String(value);
    }

    // The value of what was typed into an input; a #variable is kept as "#variable"
    function parse(text, schema) {
        const trimmed = text.trim();
        if (VARIABLE.test(trimmed)) return trimmed;
        if (schema.kind === "scalar" && schema.type === "str") return text;
        if (schema.kind === "enum") {
            const choice = schema.choices.find(c => String(c) === trimmed);
            if (choice !== undefined) return choice;
        }
        if (isNumberField(schema)) return NUMBER.test(trimmed) ? Number(trimmed) : new RawText(trimmed);
        if (schema.kind === "scalar" && schema.type === "bool") {
            if (/^true$/i.test(trimmed)) return true;
            if (/^false$/i.test(trimmed)) return false;
            return new RawText(trimmed);
        }
        return parseLoose(trimmed);
    }

    // A free-form value (of a bare dict, or a union): JSON, Python's None / True / False, or a bare word as
    // text. What looks like a number, list or dict but doesn't parse goes to the server as typed.
    function parseLoose(text) {
        try {
            return JSON.parse(text);
        } catch (e) {
            if (PYTHON_CONSTANTS.has(text)) return PYTHON_CONSTANTS.get(text);
            return /^[[{("'\d.+-]/.test(text) ? new RawText(text) : text;
        }
    }

    // Why a value would be rejected, or "" when it looks fine
    function problemWith(value, field) {
        if (!(value instanceof RawText)) return "";
        if (isNumberField(field)) return "Expected a number or a #variable";
        if (field.kind === "enum") return "Expected one of: " + field.choices.join(", ");
        return "Not a value the table can read; checked when the form is submitted";
    }

    // ------------------------------------------------------------------------
    // markup
    // ------------------------------------------------------------------------

    function el(tag, className, text) {
        const node = document.createElement(tag);
        if (className) node.className = className;
        if (text !== undefined) node.textContent = text;
        return node;
    }

    function button(icon, text, className, label) {
        const node = el("button", "btn btn-sm " + className);
        node.type = "button";  // never a submit button of the form it sits in
        node.innerHTML = `<i class="bi ${icon}" aria-hidden="true"></i>`;
        if (text) node.append(" " + text);
        if (label) {
            node.title = label;
            node.setAttribute("aria-label", label);
        }
        return node;
    }

    function typeName(schema) {
        let name = schema.type || "Any";
        if (schema.kind === "dict") name = `dict[${typeName(schema.key)}, ${typeName(schema.value)}]`;
        return schema.optional ? name + " | None" : name;
    }

    // ------------------------------------------------------------------------
    // the editor
    // ------------------------------------------------------------------------

    class StructuredEditor {
        constructor(textarea, schema) {
            this.textarea = textarea;
            this.schema = schema;
            // the form's #variable suggestions; only workflow forms have them
            this.listId = textarea.getAttribute("list");
            this.written = null;  // the textarea text this editor's value came from or wrote

            const group = textarea.closest(".input-group");
            if (group) group.classList.add("structured-group");

            // label | Fields/JSON switch | textarea | note | table: the switch sits on the label's line
            this.toolbar = el("div", "structured-toolbar structured-part");
            const switcher = el("div", "structured-switch");
            switcher.setAttribute("role", "group");
            switcher.setAttribute("aria-label", "Edit as");
            this.fieldsButton = button("bi-table", "Table", "", "Edit as a table of keys and values");
            this.jsonButton = button("bi-braces", "JSON", "", "Edit as JSON text");
            this.fieldsButton.addEventListener("click", () => this.showFields());
            this.jsonButton.addEventListener("click", () => this.showJson());
            switcher.append(this.fieldsButton, this.jsonButton);
            this.toolbar.append(switcher);

            this.note = el("div", "structured-note structured-part form-text");
            this.body = el("div", "structured-body structured-part");
            this.choiceLists = new Map();  // Enum choices, kept in the toolbar so redrawing the table keeps them

            textarea.before(this.toolbar);
            textarea.after(this.note, this.body);
            // a required value left empty: the browser can only point at the textarea while it shows
            textarea.addEventListener("invalid", () => this.showJson());
            this.showFields();
        }

        // ---- modes --------------------------------------------------------

        showFields() {
            const text = this.textarea.value;
            if (text !== this.written) {
                const read = this.read(text);
                if (read.error) {
                    this.showJson(read.error);
                    return;
                }
                this.value = read.value;
                this.written = text;
            }
            this.render();
            this.textarea.hidden = true;
            this.body.hidden = false;
            this.setNote("");
            this.setMode("fields");
        }

        showJson(note) {
            const lines = this.textarea.value.split("\n").length;
            this.textarea.rows = Math.min(Math.max(lines, 2), 20);
            this.textarea.hidden = false;
            this.body.hidden = true;
            this.setNote(note || "");
            this.setMode("json");
        }

        setMode(mode) {
            this.mode = mode;
            [[this.fieldsButton, "fields"], [this.jsonButton, "json"]].forEach(([node, name]) => {
                node.classList.toggle("active", mode === name);
                node.setAttribute("aria-pressed", String(mode === name));
            });
        }

        setNote(text) {
            this.note.textContent = text;
            this.note.hidden = !text;
        }

        // the textarea's text as a dict for the table, or why it can only be edited as text
        read(text) {
            const trimmed = text.trim();
            if (trimmed === "" || trimmed === "None") return { value: undefined };
            if (VARIABLE.test(trimmed)) {
                return { error: `The whole value is the variable ${trimmed}; clear it to fill in the table instead.` };
            }
            let value;
            try {
                value = readJson(trimmed);
            } catch (e) {
                return { error: "Shown as text because it is not JSON (a Python literal, for example). " +
                        "It is checked when the form is submitted; as JSON it can be edited as a table." };
            }
            if (!isObject(value)) return { error: "Shown as text: the table needs a dict." };
            return { value };
        }

        write() {
            this.textarea.value = this.value === undefined ? "" : serialize(this.value, this.schema);
            this.written = this.textarea.value;
            this.textarea.dispatchEvent(new Event("input", { bubbles: true }));
        }

        // ---- the table ----------------------------------------------------

        render() {
            this.body.replaceChildren();
            const root = { get: () => this.value, set: value => { this.value = value; } };
            if (this.value === undefined) {
                const empty = el("div", "structured-empty text-muted", "No value (None)");
                const fill = button("bi-plus-lg", "Set a value", "btn-outline-secondary");
                fill.addEventListener("click", () => {
                    this.value = {};
                    this.write();
                    this.render();
                    this.body.querySelector(".structured-add-row")?.focus();
                });
                empty.append(fill);
                this.body.append(empty);
            } else {
                const holder = el("div", "structured-collection");
                this.body.append(holder);
                this.renderDict(holder, this.schema, root);
            }
            if (this.listId) this.body.append(el("div", "form-text structured-hint", "Any value can be a #variable."));
        }

        // the table's last steps: the empty-table line, the add button, focus after a change
        finishTable(holder, node, columns, empty, add, focus) {
            if (!node.tBodies[0].rows.length) {
                const tr = el("tr");
                const td = el("td", "structured-no-rows", empty);
                td.colSpan = columns;
                tr.append(td);
                node.tBodies[0].append(tr);
            }
            const wrap = el("div", "structured-table-wrap");
            wrap.append(node);
            holder.append(wrap, add);
            if (!focus) return;
            const tr = node.tBodies[0].rows[focus.row];
            const target = focus.row < 0 || !tr ? add
                : focus.action === "input" ? tr.querySelector("input")
                : tr.querySelector(`[data-action="${focus.action}"]`);
            (target || add).focus();
            if (target && target.select) target.select();
        }

        // a dict: a table of keys and values, and buttons to add and remove entries. Renaming a key keeps
        // the entry where it is.
        renderDict(holder, schema, slot, focus) {
            holder.replaceChildren();
            const object = isObject(slot.get()) ? slot.get() : null;
            const keys = object ? Object.keys(object) : [];
            const numberKeys = isNumberField(schema.key);
            // a nested dict is held in one cell, as JSON
            const valueField = Object.assign({}, schema.value, { name: "value" },
                schema.value.kind === "dict" ? { kind: "json" } : {});
            const change = (edit, focusAfter) => {
                if (!isObject(slot.get())) slot.set({});
                edit(slot.get());
                this.write();
                this.renderDict(holder, schema, slot, focusAfter);
            };
            const rename = (from, to) => {
                const current = slot.get();
                const entries = Object.keys(current).map(key => [key === from ? to : key, current[key]]);
                Object.keys(current).forEach(key => delete current[key]);
                entries.forEach(([key, value]) => { current[key] = value; });
            };

            const node = el("table", "structured-table");
            const head = el("tr");
            const keyHead = el("th", "", "Key");
            const valueHead = el("th", "", "Value");
            const actionsHead = el("th", "structured-row-actions");
            keyHead.title = `key: ${typeName(schema.key)}`;
            valueHead.title = `value: ${typeName(schema.value)}`;
            actionsHead.append(el("span", "visually-hidden", "Row actions"));
            head.append(keyHead, valueHead, actionsHead);
            node.append(el("thead"), el("tbody"));
            node.tHead.append(head);

            keys.forEach((key, i) => {
                const entry = { key };  // the entry's current key, for the value input after a rename
                const tr = el("tr");
                const keyCell = el("td", "structured-key");
                const keyInput = el("input", "form-control form-control-sm");
                keyInput.type = "text";
                keyInput.autocomplete = "off";
                keyInput.spellcheck = false;
                keyInput.value = key;
                keyInput.dataset.column = "key";
                keyInput.setAttribute("aria-label", `Key, row ${i + 1}`);
                keyInput.addEventListener("input", () => {
                    const typed = keyInput.value.trim();
                    const taken = typed !== entry.key && Object.prototype.hasOwnProperty.call(slot.get(), typed);
                    const problem = !typed ? "A key is needed" : taken ? "Another entry has this key"
                        : numberKeys && !NUMBER.test(typed) ? "Expected a number" : "";
                    keyInput.classList.toggle("is-invalid", !!problem);
                    keyInput.title = problem;
                    if (problem) return;  // the entry keeps its last good key until this one is fixed
                    rename(entry.key, typed);
                    entry.key = typed;
                    this.write();
                });
                this.moveDownOnEnter(keyInput);
                keyCell.append(keyInput);

                const valueCell = el("td");
                const valueInput = this.input(valueField, object[key], v => {
                    slot.get()[entry.key] = v;
                });
                valueInput.dataset.column = "value";
                valueInput.setAttribute("aria-label", `Value, row ${i + 1}`);
                valueCell.append(valueInput);

                const actions = el("td", "structured-row-actions");
                const remove = button("bi-x-lg", "", "btn-link structured-icon structured-remove", `Remove row ${i + 1}`);
                remove.dataset.action = "remove";
                remove.addEventListener("click", () => change(current => { delete current[entry.key]; },
                    { row: Math.min(i, keys.length - 2), action: "remove" }));
                actions.append(remove);
                tr.append(keyCell, valueCell, actions);
                node.tBodies[0].append(tr);
            });

            const add = button("bi-plus-lg", "Add entry", "structured-add-row");
            add.addEventListener("click", () => {
                let n = keys.length + 1;
                while (object && Object.prototype.hasOwnProperty.call(object, numberKeys ? String(n) : `key${n}`)) n++;
                change(current => { current[numberKeys ? String(n) : `key${n}`] = templateFor(schema.value); },
                    { row: keys.length, action: "input" });
            });
            this.finishTable(holder, node, 3, slot.get() == null ? "None" : "No entries", add, focus);
        }

        // an input for one value; set(value) stores what was typed (None when emptied)
        input(field, value, set) {
            const input = el("input", "form-control form-control-sm");
            input.type = "text";
            input.id = `structured-input-${++lastId}`;
            input.autocomplete = "off";
            input.spellcheck = false;
            input.value = display(value, field);
            if (field.kind === "enum") {
                input.setAttribute("list", this.choiceList(field));
            } else if (this.listId) {
                input.setAttribute("list", this.listId);
            }
            const flag = current => {
                const problem = problemWith(current, field);
                input.classList.toggle("is-invalid", !!problem);
                input.title = `value: ${typeName(field)}` + (problem ? `\n${problem}` : "");
            };
            flag(value);
            input.addEventListener("input", () => {
                const typed = input.value.trim() === "" ? null : parse(input.value, field);
                set(typed);
                flag(typed);
                this.write();
            });
            this.moveDownOnEnter(input);
            return input;
        }

        // in the table, Enter moves down a row like a spreadsheet, rather than submitting the form
        moveDownOnEnter(input) {
            input.addEventListener("keydown", event => {
                if (event.key !== "Enter" || !input.dataset.column) return;
                event.preventDefault();
                const next = input.closest("tr").nextElementSibling;
                next?.querySelector(`input[data-column="${input.dataset.column}"]`)?.focus();
            });
        }

        // the choices of an Enum value, one datalist per editor
        choiceList(field) {
            const key = `${field.type}:${field.choices.join("|")}`;
            if (!this.choiceLists.has(key)) {
                const list = el("datalist");
                list.id = `structured-choices-${++lastId}`;
                field.choices.forEach(choice => {
                    const option = el("option");
                    option.value = String(choice);
                    list.append(option);
                });
                this.toolbar.append(list);
                this.choiceLists.set(key, list.id);
            }
            return this.choiceLists.get(key);
        }
    }

    // ------------------------------------------------------------------------
    // setup: forms arrive with the page and later as HTML (toolbox groups, step pop-ups)
    // ------------------------------------------------------------------------

    function enhance(textarea) {
        if (editors.has(textarea)) return;
        let schema;
        try {
            schema = JSON.parse(textarea.dataset.schema);
        } catch (e) {
            return;  // no layout: stays a JSON box
        }
        if (!schema || schema.kind !== "dict") return;
        // a copy of an enhanced form brings the old editor's markup along, without its handlers
        Array.from(textarea.parentElement ? textarea.parentElement.children : []).forEach(node => {
            if (node.classList.contains("structured-part")) node.remove();
        });
        editors.set(textarea, new StructuredEditor(textarea, schema));
    }

    function enhanceAll(root) {
        if (root.matches && root.matches("textarea[data-schema]")) enhance(root);
        if (root.querySelectorAll) root.querySelectorAll("textarea[data-schema]").forEach(enhance);
    }

    function start() {
        enhanceAll(document);
        new MutationObserver(mutations => {
            mutations.forEach(mutation => mutation.addedNodes.forEach(node => {
                if (node.nodeType === Node.ELEMENT_NODE) enhanceAll(node);
            }));
        }).observe(document.body, { childList: true, subtree: true });
    }

    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start);
    else start();

    window.StructuredEditor = { enhance, enhanceAll, serialize, parse };
})();
