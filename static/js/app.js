/* AJAPRA — interface web. Consome a API REST do backend (JSON). Sem dependências externas. */
(() => {
"use strict";

/* ============================ Utilidades ============================ */
const $ = (sel, el = document) => el.querySelector(sel);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const CSRF = $('meta[name="csrf-token"]').content;
const ME = { perfil: document.body.dataset.perfil, nome: document.body.dataset.nome };
const IS_ADMIN = ME.perfil === "admin";

const MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];
const MESES_LONGOS = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"];
const fmtMes = (ym) => `${MESES[+ym.slice(5, 7) - 1]}/${ym.slice(2, 4)}`;
const fmtData = (iso) => (iso ? iso.split("-").reverse().join("/") : "—");
const fmtCpf = (c) => (c && c.length === 11 ? `${c.slice(0, 3)}.${c.slice(3, 6)}.${c.slice(6, 9)}-${c.slice(9)}` : c || "—");
const fmtTel = (t) => (t && t.length >= 10 ? `(${t.slice(0, 2)}) ${t.slice(2, t.length - 4)}-${t.slice(-4)}` : t || "—");
const fmtIdade = (m) => (m === null || m === undefined || m === "" ? "—" : m < 12 ? `${m} m` : `${Math.floor(m / 12)} a${m % 12 ? ` ${m % 12} m` : ""}`);
const fmtNum = (n, d = 0) => (n === null || n === undefined ? "—" : Number(n).toLocaleString("pt-BR", { minimumFractionDigits: d, maximumFractionDigits: d }));
const isoToday = () => { const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`; };
const debounce = (fn, ms = 250) => { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; };

const L = {
  cachorro: "Cachorro", gato: "Gato", outro: "Outro", macho: "Macho", femea: "Fêmea",
  pequeno: "Pequeno", medio: "Médio", grande: "Grande", sim: "Sim", nao: "Não",
  disponivel: "Disponível", em_tratamento: "Em tratamento", adotado: "Adotado",
  feira_adocao: "Feira de adoção", vacinacao: "Vacinação", castracao: "Castração", campanha: "Campanha",
  arrecadacao: "Arrecadação", reuniao: "Reunião", planejada: "Planejada", realizada: "Realizada",
  cancelada: "Cancelada", admin: "Administrador", voluntario: "Voluntário", true: "Ativo", false: "Inativo",
};
const lab = (v) => L[v] ?? (v === "" || v == null ? "—" : String(v));
const opts = (keys) => keys.map((k) => ({ value: k, label: lab(k) }));
const badge = (v) => `<span class="badge ${esc(v)}">${esc(lab(v))}</span>`;

async function api(method, url, body) {
  const init = { method, credentials: "same-origin", headers: { "X-CSRF-Token": CSRF } };
  if (body !== undefined) { init.headers["Content-Type"] = "application/json"; init.body = JSON.stringify(body); }
  const resp = await fetch(url, init);
  if (resp.status === 401) { location.href = "/login"; throw new Error("Sessão expirada."); }
  const data = await resp.json().catch(() => ({}));
  if (!resp.ok) { const e = new Error(data.erro || "Erro inesperado."); e.fields = data.campos || {}; throw e; }
  return data;
}

function toast(msg, kind = "ok") {
  const el = document.createElement("div");
  el.className = `toast ${kind === "error" ? "error" : ""}`;
  el.textContent = msg;
  $("#toasts").appendChild(el);
  setTimeout(() => el.remove(), kind === "error" ? 6000 : 3000);
}
const fail = (e) => toast(e.message || "Erro inesperado.", "error");

/* ============================ Diálogos ============================ */
function fieldHtml(f, values) {
  const v = values[f.name] ?? f.default ?? "";
  const id = `f-${f.name}`;
  const common = `id="${id}" name="${esc(f.name)}" ${f.required ? "required" : ""} ${f.disabled ? "disabled" : ""}`;
  let control;
  if (f.type === "select") {
    const blank = f.required ? "" : `<option value="">—</option>`;
    control = `<select ${common}>${blank}${(f.options || []).map((o) =>
      `<option value="${esc(o.value)}" ${String(o.value) === String(v) ? "selected" : ""}>${esc(o.label)}</option>`).join("")}</select>`;
  } else if (f.type === "textarea") {
    control = `<textarea ${common} maxlength="${f.max || 500}">${esc(v)}</textarea>`;
  } else {
    control = `<input ${common} type="${f.type || "text"}" value="${esc(v)}" ${f.max ? `maxlength="${f.max}"` : ""}
      ${f.inputmode ? `inputmode="${f.inputmode}"` : ""} ${f.type === "number" ? `min="${f.min ?? 0}" max="${f.maxv ?? ""}"` : ""}
      ${f.autocomplete ? `autocomplete="${f.autocomplete}"` : ""}>`;
  }
  return `<label class="field ${f.wide ? "wide" : ""}"><span>${esc(f.label)}${f.required ? " *" : ""}</span>${control}
    <small class="err" data-err="${esc(f.name)}"></small></label>`;
}

async function openForm({ title, fields, values = {}, hint = "", submitLabel = "Salvar", onSubmit }) {
  const resolved = await Promise.all(fields.map(async (f) => ({ ...f, options: typeof f.options === "function" ? await f.options() : f.options })));
  const dlg = document.createElement("dialog");
  dlg.className = "modal";
  dlg.innerHTML = `<form class="form" novalidate>
    <header><h2>${esc(title)}</h2><button type="button" class="icon" data-close aria-label="Fechar">×</button></header>
    <div class="grid">${resolved.map((f) => fieldHtml(f, values)).join("")}</div>
    ${hint ? `<p class="hint">${esc(hint)}</p>` : ""}
    <p class="form-error" role="alert" hidden></p>
    <footer><button type="button" class="btn" data-close>Cancelar</button><button type="submit" class="btn primary">${esc(submitLabel)}</button></footer>
  </form>`;
  document.body.appendChild(dlg);
  dlg.addEventListener("close", () => dlg.remove());
  dlg.addEventListener("click", (e) => { if (e.target.closest("[data-close]")) dlg.close(); });
  const form = $("form", dlg), errBox = $(".form-error", dlg), btn = $('button[type="submit"]', dlg);
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    errBox.hidden = true;
    dlg.querySelectorAll(".err").forEach((s) => (s.textContent = ""));
    const data = {};
    resolved.forEach((f) => { if (!f.disabled) data[f.name] = form.elements[f.name].value; });
    btn.disabled = true;
    try { await onSubmit(data); dlg.close(); }
    catch (err) {
      errBox.textContent = err.message; errBox.hidden = false;
      Object.entries(err.fields || {}).forEach(([k, m]) => { const s = dlg.querySelector(`[data-err="${CSS.escape(k)}"]`); if (s) s.textContent = m; });
    } finally { btn.disabled = false; }
  });
  dlg.showModal();
  const first = form.querySelector("input:not([disabled]), select:not([disabled])");
  if (first) first.focus();
}

function confirmBox(message, okLabel = "Excluir") {
  return new Promise((resolve) => {
    const dlg = document.createElement("dialog");
    dlg.className = "modal";
    dlg.innerHTML = `<div class="form"><h2>Confirmação</h2><p>${esc(message)}</p>
      <footer><button class="btn" data-v="0">Cancelar</button><button class="btn danger" data-v="1">${esc(okLabel)}</button></footer></div>`;
    document.body.appendChild(dlg);
    dlg.addEventListener("click", (e) => { const b = e.target.closest("[data-v]"); if (b) { dlg.returnValue = b.dataset.v; dlg.close(); } });
    dlg.addEventListener("close", () => { resolve(dlg.returnValue === "1"); dlg.remove(); });
    dlg.showModal();
  });
}

/* ============================ Gráficos (SVG) ============================ */
function niceMax(v) {  // limite superior com 4 divisões em valores inteiros "redondos"
  const p = Math.pow(10, Math.floor(Math.log10(Math.max(v, 1) / 4)));
  let step = 1;
  for (const m of [1, 2, 3, 4, 5, 6, 8, 10]) { step = Math.max(1, m * p); if (step * 4 >= v) break; }
  return step * 4;
}

function yAxis(l, r, t, ih, W, max) {
  let g = "";
  for (let i = 0; i <= 4; i++) {
    const y = t + ih - (ih * i) / 4;
    g += `<line class="gl" x1="${l}" x2="${W - r}" y1="${y}" y2="${y}"/><text class="axis" x="${l - 6}" y="${y + 4}" text-anchor="end">${Math.round((max * i) / 4)}</text>`;
  }
  return g;
}

function barChart(el, labels, series) {
  const W = 720, H = 260, l = 38, r = 8, t = 12, b = 30, iw = W - l - r, ih = H - t - b;
  const max = niceMax(Math.max(1, ...series.flatMap((s) => s.values)));
  const gw = iw / labels.length, bw = Math.min(26, (gw * 0.8) / series.length), step = Math.ceil(labels.length / 12);
  let g = yAxis(l, r, t, ih, W, max);
  labels.forEach((lb, i) => {
    const gx = l + i * gw + (gw - bw * series.length) / 2;
    series.forEach((s, k) => {
      const h = (ih * s.values[i]) / max;
      g += `<rect class="bar s${k}" x="${gx + k * bw}" y="${t + ih - h}" width="${Math.max(bw - 1, 1)}" height="${h}" rx="2"><title>${esc(fmtMes(lb))} · ${esc(s.name)}: ${s.values[i]}</title></rect>`;
    });
    if (i % step === 0) g += `<text class="axis" x="${l + i * gw + gw / 2}" y="${H - 10}" text-anchor="middle">${esc(fmtMes(lb))}</text>`;
  });
  el.innerHTML = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Gráfico de barras mensal">${g}</svg>
    <div class="legend">${series.map((s, k) => `<span><i class="sw s${k}"></i>${esc(s.name)}</span>`).join("")}</div>`;
}

function hBars(el, items, labelFn = (x) => x) {
  if (!items.length) { el.innerHTML = `<p class="hint">Sem dados no período.</p>`; return; }
  const max = Math.max(...items.map((i) => i.valor));
  el.innerHTML = `<div class="hbars">${items.map((i) => `<div class="hbar"><span>${esc(labelFn(i.nome))}</span>
    <svg viewBox="0 0 100 12" preserveAspectRatio="none" role="img" aria-label="${esc(labelFn(i.nome))}: ${i.valor}"><rect class="bg" width="100" height="12" rx="3"/><rect width="${(i.valor / max) * 100}" height="12" rx="3"/></svg>
    <b>${i.valor}</b></div>`).join("")}</div>`;
}

function forecastChart(el, hist, fc) {
  const show = hist.slice(-24), n = show.length, all = n + fc.length;
  const W = 720, H = 300, l = 38, r = 28, t = 14, b = 30, iw = W - l - r, ih = H - t - b;
  const max = niceMax(Math.max(1, ...show.map((h) => h.valor), ...fc.map((f) => f.maximo)));
  const x = (i) => l + (iw * i) / (all - 1), y = (v) => t + ih - (ih * v) / max;
  const last = show[n - 1];
  const pHist = show.map((h, i) => `${i ? "L" : "M"}${x(i)},${y(h.valor)}`).join(" ");
  const pFc = `M${x(n - 1)},${y(last.valor)} ` + fc.map((f, j) => `L${x(n + j)},${y(f.estimativa)}`).join(" ");
  const up = fc.map((f, j) => `L${x(n + j)},${y(f.maximo)}`).join(" ");
  const low = [...fc].map((f, j) => [j, f]).reverse().map(([j, f]) => `L${x(n + j)},${y(f.minimo)}`).join(" ");
  const band = `M${x(n - 1)},${y(last.valor)} ${up} ${low} Z`;
  const all_labels = [...show.map((h) => h.mes), ...fc.map((f) => f.mes)], step = Math.ceil(all / 12);
  let g = yAxis(l, r, t, ih, W, max);
  g += `<rect class="fc-zone" x="${x(n - 1)}" y="${t}" width="${x(all - 1) - x(n - 1)}" height="${ih}"/>`;
  g += `<path class="band" d="${band}"/><path class="line-hist" d="${pHist}"/><path class="line-fc" d="${pFc}"/>`;
  show.forEach((h, i) => { g += `<circle class="dot-h" cx="${x(i)}" cy="${y(h.valor)}" r="3"><title>${esc(fmtMes(h.mes))}: ${h.valor} cadastros</title></circle>`; });
  fc.forEach((f, j) => { g += `<circle class="dot-f" cx="${x(n + j)}" cy="${y(f.estimativa)}" r="4.5"><title>${esc(fmtMes(f.mes))}: ~${f.inteiro} (entre ${f.minimo} e ${f.maximo})</title></circle>`; });
  all_labels.forEach((m, i) => { if (i % step === 0 || i === all - 1) g += `<text class="axis" x="${x(i)}" y="${H - 10}" text-anchor="middle">${esc(fmtMes(m))}</text>`; });
  el.innerHTML = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Histórico de cadastros e previsão dos próximos meses">${g}</svg>
    <div class="legend"><span><i class="sw s0"></i>Cadastros realizados</span><span><i class="sw s1"></i>Estimativa</span><span>Faixa sombreada: intervalo de 80%</span></div>`;
}

/* ============================ Páginas CRUD genéricas ============================ */
function filterHtml(f) {
  const id = `flt-${f.name}`;
  let control;
  if (f.type === "select") control = `<select id="${id}" name="${f.name}"><option value="">Todos</option>${f.options.map((o) => `<option value="${esc(o.value)}">${esc(o.label)}</option>`).join("")}</select>`;
  else control = `<input id="${id}" name="${f.name}" type="${f.type || "search"}" placeholder="${esc(f.placeholder || "")}" autocomplete="off">`;
  return `<label class="field ${f.grow ? "grow" : ""}"><span>${esc(f.label)}</span>${control}</label>`;
}

function crudPage(cfg) {
  const root = $("#app");
  const canDelete = cfg.deleteAll || IS_ADMIN;
  root.innerHTML = `
    <div class="page-head"><div><h1>${esc(cfg.title)}</h1><p class="sub">${esc(cfg.subtitle || "")}</p></div>
      <button class="btn primary" id="btn-new">+ ${esc(cfg.newLabel || "Novo")}</button></div>
    <form class="filters card" id="filters" autocomplete="off" ${(cfg.filters || []).length ? "" : "hidden"}>${(cfg.filters || []).map(filterHtml).join("")}<button class="btn ghost" type="reset">Limpar</button></form>
    <div class="card table-card"><div class="table-scroll" id="table"></div><p class="count" id="count"></p></div>`;
  let rows = [];

  const load = async () => {
    const qs = new URLSearchParams();
    new FormData($("#filters")).forEach((v, k) => { if (String(v).trim()) qs.append(k, String(v).trim()); });
    try { rows = await api("GET", `${cfg.endpoint}?${qs}`); render(); } catch (e) { fail(e); }
  };

  const render = () => {
    const wrap = $("#table");
    $("#count").textContent = `${rows.length} registro${rows.length === 1 ? "" : "s"}`;
    if (!rows.length) { wrap.innerHTML = `<p class="empty">Nenhum registro encontrado.</p>`; return; }
    const showActions = !cfg.noEdit || canDelete;
    wrap.innerHTML = `<table><thead><tr>${cfg.columns.map((c) => `<th>${esc(c.label)}</th>`).join("")}${showActions ? "<th></th>" : ""}</tr></thead>
      <tbody>${rows.map((r) => `<tr>${cfg.columns.map((c) => `<td>${c.render(r)}</td>`).join("")}${showActions ? `<td class="actions">
        ${cfg.noEdit ? "" : `<button class="btn small" data-act="edit" data-id="${esc(r.id)}">Editar</button>`}
        ${canDelete ? `<button class="btn small danger" data-act="del" data-id="${esc(r.id)}">Excluir</button>` : ""}</td>` : ""}</tr>`).join("")}</tbody></table>`;
  };

  const fieldsFor = (row) => (typeof cfg.fields === "function" ? cfg.fields(row) : cfg.fields);

  $("#btn-new").addEventListener("click", () => openForm({
    title: cfg.newLabel || "Novo registro", fields: fieldsFor(null), values: cfg.defaults ? cfg.defaults() : {}, hint: cfg.formHint,
    onSubmit: async (d) => { await api("POST", cfg.endpoint, d); toast("Registro salvo."); load(); },
  }).catch(fail));

  $("#table").addEventListener("click", async (e) => {
    const b = e.target.closest("button[data-act]");
    if (!b) return;
    const row = rows.find((r) => r.id === b.dataset.id);
    if (!row) return;
    if (b.dataset.act === "edit") {
      openForm({ title: `Editar — ${cfg.rowName(row)}`, fields: fieldsFor(row), values: row,
        onSubmit: async (d) => { await api("PUT", `${cfg.endpoint}/${row.id}`, d); toast("Alterações salvas."); load(); } }).catch(fail);
    } else if (await confirmBox(`Excluir "${cfg.rowName(row)}"? Esta ação não pode ser desfeita.${cfg.deleteNote ? " " + cfg.deleteNote : ""}`)) {
      try { await api("DELETE", `${cfg.endpoint}/${row.id}`); toast("Registro excluído."); load(); } catch (err) { fail(err); }
    }
  });

  const f = $("#filters");
  f.addEventListener("input", debounce(load));
  f.addEventListener("change", load);
  f.addEventListener("reset", () => setTimeout(load, 0));
  f.addEventListener("submit", (e) => e.preventDefault());
  load();
}

/* ---------- Animais ---------- */
const pageAnimais = () => crudPage({
  title: "Animais", subtitle: "Cadastro e consulta dos animais da ONG.", endpoint: "/api/animais", newLabel: "Novo animal",
  rowName: (r) => r.nome,
  filters: [
    { name: "q", label: "Buscar", placeholder: "Nome, cor ou descrição", grow: true },
    { name: "especie", label: "Espécie", type: "select", options: opts(["cachorro", "gato", "outro"]) },
    { name: "status", label: "Status", type: "select", options: opts(["disponivel", "em_tratamento", "adotado"]) },
    { name: "porte", label: "Porte", type: "select", options: opts(["pequeno", "medio", "grande"]) },
  ],
  columns: [
    { label: "Nome", render: (r) => `<b>${esc(r.nome)}</b><small>${esc(r.cor || "")}</small>` },
    { label: "Espécie", render: (r) => esc(lab(r.especie)) },
    { label: "Sexo / porte", render: (r) => `${esc(lab(r.sexo))}<small>${esc(lab(r.porte))}</small>` },
    { label: "Idade", render: (r) => esc(fmtIdade(r.idade_meses)) },
    { label: "Castrado", render: (r) => esc(lab(r.castrado)) },
    { label: "Status", render: (r) => badge(r.status) },
    { label: "Cadastro", render: (r) => esc(fmtData(r.data_cadastro)) },
  ],
  defaults: () => ({ data_cadastro: isoToday(), status: "disponivel" }),
  fields: (row) => [
    { name: "nome", label: "Nome", required: true, max: 80 },
    { name: "especie", label: "Espécie", type: "select", required: true, options: opts(["cachorro", "gato", "outro"]) },
    { name: "sexo", label: "Sexo", type: "select", required: true, options: opts(["macho", "femea"]) },
    { name: "porte", label: "Porte", type: "select", required: true, options: opts(["pequeno", "medio", "grande"]) },
    { name: "idade_meses", label: "Idade (meses)", type: "number", min: 0, maxv: 360 },
    { name: "cor", label: "Cor", max: 40 },
    { name: "castrado", label: "Castrado", type: "select", options: opts(["sim", "nao"]) },
    { name: "status", label: "Status", type: "select", required: true,
      options: row && row.status === "adotado" ? opts(["adotado"]) : opts(["disponivel", "em_tratamento"]), disabled: !!row && row.status === "adotado" },
    { name: "data_cadastro", label: "Data de cadastro", type: "date" },
    { name: "descricao", label: "Descrição", type: "textarea", wide: true },
  ],
});

/* ---------- Adotantes ---------- */
const pageAdotantes = () => crudPage({
  title: "Adotantes", subtitle: "Pessoas que adotaram (ou querem adotar). Contém dados pessoais — manuseie conforme a LGPD.",
  endpoint: "/api/adotantes", newLabel: "Novo adotante", rowName: (r) => r.nome,
  filters: [
    { name: "q", label: "Buscar", placeholder: "Nome, CPF ou e-mail", grow: true },
    { name: "cidade", label: "Cidade", placeholder: "Ex.: Jaraguá do Sul" },
  ],
  columns: [
    { label: "Nome", render: (r) => `<b>${esc(r.nome)}</b><small>${esc(r.email || "")}</small>` },
    { label: "CPF", render: (r) => esc(fmtCpf(r.cpf)) },
    { label: "Telefone", render: (r) => esc(fmtTel(r.telefone)) },
    { label: "Cidade", render: (r) => `${esc(r.cidade)}${r.uf ? ` / ${esc(r.uf)}` : ""}<small>${esc(r.endereco || "")}</small>` },
  ],
  defaults: () => ({ uf: "SC" }),
  fields: () => [
    { name: "nome", label: "Nome completo", required: true, max: 120, wide: true },
    { name: "cpf", label: "CPF", required: true, inputmode: "numeric", max: 14 },
    { name: "telefone", label: "Telefone (com DDD)", required: true, inputmode: "tel", max: 16 },
    { name: "email", label: "E-mail", type: "email", max: 120 },
    { name: "cidade", label: "Cidade", required: true, max: 80 },
    { name: "uf", label: "UF", max: 2 },
    { name: "endereco", label: "Endereço", max: 200 },
    { name: "observacoes", label: "Observações", type: "textarea", wide: true },
  ],
});

/* ---------- Adoções ---------- */
const pageAdocoes = () => crudPage({
  title: "Adoções", subtitle: "Registro das adoções realizadas. Ao registrar, o animal passa para “Adotado”.",
  endpoint: "/api/adocoes", newLabel: "Registrar adoção", noEdit: true, rowName: (r) => `${r.animal_nome} → ${r.adotante_nome}`,
  deleteNote: "O animal voltará a ficar disponível.",
  filters: [
    { name: "q", label: "Buscar", placeholder: "Nome do adotante ou do animal", grow: true },
    { name: "cidade", label: "Cidade" },
    { name: "especie", label: "Espécie", type: "select", options: opts(["cachorro", "gato", "outro"]) },
    { name: "de", label: "De", type: "date" },
    { name: "ate", label: "Até", type: "date" },
  ],
  columns: [
    { label: "Data", render: (r) => esc(fmtData(r.data_adocao)) },
    { label: "Animal", render: (r) => `<b>${esc(r.animal_nome)}</b><small>${esc(lab(r.animal_especie))}</small>` },
    { label: "Adotante", render: (r) => esc(r.adotante_nome) },
    { label: "Cidade", render: (r) => esc(r.cidade || "—") },
    { label: "Observações", render: (r) => esc(r.observacoes || "") },
  ],
  defaults: () => ({ data_adocao: isoToday() }),
  formHint: "Só aparecem animais com status “Disponível”. Adotante não encontrado? Cadastre-o primeiro em Adotantes.",
  fields: () => [
    { name: "animal_id", label: "Animal", type: "select", required: true, wide: true,
      options: async () => [{ value: "", label: "Selecione…" }, ...(await api("GET", "/api/animais?status=disponivel")).map((a) => ({ value: a.id, label: `${a.nome} (${lab(a.especie)}, ${fmtIdade(a.idade_meses)})` }))] },
    { name: "adotante_id", label: "Adotante", type: "select", required: true, wide: true,
      options: async () => [{ value: "", label: "Selecione…" }, ...(await api("GET", "/api/adotantes")).map((a) => ({ value: a.id, label: `${a.nome} — ${a.cidade}` }))] },
    { name: "data_adocao", label: "Data da adoção", type: "date", required: true },
    { name: "observacoes", label: "Observações", type: "textarea", wide: true },
  ],
});

/* ---------- Usuários (admin) ---------- */
const pageUsuarios = () => crudPage({
  title: "Usuários", subtitle: "Quem pode acessar o sistema. Voluntários não podem excluir registros.",
  endpoint: "/api/usuarios", newLabel: "Novo usuário", rowName: (r) => r.nome,
  filters: [],
  columns: [
    { label: "Nome", render: (r) => `<b>${esc(r.nome)}</b>` },
    { label: "E-mail", render: (r) => esc(r.email) },
    { label: "Perfil", render: (r) => esc(lab(r.perfil)) },
    { label: "Situação", render: (r) => badge(String(r.ativo !== false)) },
  ],
  defaults: () => ({ perfil: "voluntario", ativo: "true" }),
  fields: (row) => [
    { name: "nome", label: "Nome", required: true, max: 80 },
    { name: "email", label: "E-mail", type: "email", required: true, max: 120, autocomplete: "off" },
    { name: "perfil", label: "Perfil", type: "select", required: true, options: opts(["voluntario", "admin"]) },
    { name: "ativo", label: "Situação", type: "select", required: true, options: [{ value: "true", label: "Ativo" }, { value: "false", label: "Inativo" }] },
    { name: "senha", label: row ? "Nova senha (deixe em branco para manter)" : "Senha (mín. 8 caracteres)", type: "password", required: !row, max: 128, autocomplete: "new-password", wide: true },
  ],
});

/* ============================ Painel ============================ */
async function pageDashboard() {
  const root = $("#app");
  root.innerHTML = `<div class="page-head"><div><h1>Painel</h1><p class="sub">Olá, ${esc(ME.nome.split(" ")[0])}. Resumo da ONG hoje.</p></div></div><p class="loading">Carregando…</p>`;
  let d;
  try { d = await api("GET", "/api/dashboard"); } catch (e) { return fail(e); }
  const t = d.totais;
  root.innerHTML = `
    <div class="page-head"><div><h1>Painel</h1><p class="sub">Olá, ${esc(ME.nome.split(" ")[0])}. Resumo da ONG hoje.</p></div>
      <a class="btn primary" href="/previsao">Ver previsão</a></div>
    <div class="stats">
      <div class="stat accent"><b>${fmtNum(t.disponiveis)}</b><span>Animais disponíveis</span></div>
      <div class="stat"><b>${fmtNum(t.em_tratamento)}</b><span>Em tratamento</span></div>
      <div class="stat"><b>${fmtNum(t.adotados)}</b><span>Adotados (total)</span></div>
      <div class="stat warm"><b>${fmtNum(t.adocoes_mes)}</b><span>Adoções neste mês</span></div>
      <div class="stat"><b>${fmtNum(t.cadastros_mes)}</b><span>Cadastros neste mês</span></div>
      <div class="stat"><b>${fmtNum(t.adotantes)}</b><span>Adotantes cadastrados</span></div>
    </div>
    <div class="grid-2">
      <section class="card"><h2>Últimos 12 meses</h2><div id="chart"></div></section>
      <section class="card"><h2>Próximas atividades</h2><div id="next"></div></section>
    </div>`;
  barChart($("#chart"), d.serie.meses, [{ name: "Animais cadastrados", values: d.serie.cadastros }, { name: "Adoções", values: d.serie.adocoes }]);
  $("#next").innerHTML = d.proximas_atividades.length
    ? `<ul class="list">${d.proximas_atividades.map((a) => `<li><time>${esc(fmtData(a.data).slice(0, 5))}</time><span><b>${esc(a.titulo)}</b><small class="hint"> ${esc(a.horario || "")} ${esc(a.local ? "· " + a.local : "")}</small></span></li>`).join("")}</ul>`
    : `<p class="hint">Nenhuma atividade planejada. Adicione no <a href="/atividades">calendário</a>.</p>`;
}

/* ============================ Calendário ============================ */
function pageAtividades() {
  const root = $("#app");
  const now = new Date();
  let cur = { y: now.getFullYear(), m: now.getMonth() };
  let rows = [];
  const pad = (n) => String(n).padStart(2, "0");

  const fields = () => [
    { name: "titulo", label: "Título", required: true, max: 120, wide: true },
    { name: "tipo", label: "Tipo", type: "select", required: true, options: opts(["feira_adocao", "vacinacao", "castracao", "campanha", "arrecadacao", "reuniao", "outro"]) },
    { name: "status", label: "Situação", type: "select", required: true, options: opts(["planejada", "realizada", "cancelada"]) },
    { name: "data", label: "Data", type: "date", required: true },
    { name: "horario", label: "Horário", type: "time" },
    { name: "local", label: "Local", max: 120 },
    { name: "responsavel", label: "Responsável", max: 80 },
    { name: "descricao", label: "Descrição", type: "textarea", wide: true },
  ];

  root.innerHTML = `
    <div class="page-head"><div><h1>Calendário de atividades</h1><p class="sub">Feiras, campanhas, mutirões e reuniões.</p></div>
      <button class="btn primary" id="btn-new">+ Nova atividade</button></div>
    <div class="card"><div class="cal-head">
      <button class="btn" id="prev" aria-label="Mês anterior">‹</button><h2 id="mes"></h2><button class="btn" id="next" aria-label="Próximo mês">›</button>
      <button class="btn ghost" id="hoje">Hoje</button></div><div id="cal" class="cal"></div></div>
    <div class="card table-card pad-top"><div class="table-scroll" id="lista"></div></div>`;

  async function load() {
    const first = `${cur.y}-${pad(cur.m + 1)}-01`;
    const lastDay = new Date(cur.y, cur.m + 1, 0).getDate();
    try { rows = await api("GET", `/api/atividades?de=${first}&ate=${cur.y}-${pad(cur.m + 1)}-${pad(lastDay)}`); } catch (e) { return fail(e); }
    render();
  }

  function render() {
    $("#mes").textContent = `${MESES_LONGOS[cur.m][0].toUpperCase()}${MESES_LONGOS[cur.m].slice(1)} de ${cur.y}`;
    const startDow = new Date(cur.y, cur.m, 1).getDay(), days = new Date(cur.y, cur.m + 1, 0).getDate();
    const prevDays = new Date(cur.y, cur.m, 0).getDate(), today = isoToday();
    const byDay = {};
    rows.forEach((r) => (byDay[r.data] = [...(byDay[r.data] || []), r]));
    let html = ["Dom", "Seg", "Ter", "Qua", "Qui", "Sex", "Sáb"].map((d) => `<div class="dow">${d}</div>`).join("");
    for (let i = 0; i < startDow; i++) html += `<div class="day out"><span class="n">${prevDays - startDow + 1 + i}</span></div>`;
    for (let d = 1; d <= days; d++) {
      const iso = `${cur.y}-${pad(cur.m + 1)}-${pad(d)}`;
      html += `<div class="day ${iso === today ? "today" : ""}" data-date="${iso}"><span class="n">${d}</span>${(byDay[iso] || []).map((a) =>
        `<button class="chip ${esc(a.tipo)} ${esc(a.status)}" data-id="${esc(a.id)}" title="${esc(a.titulo)}">${esc(a.horario ? a.horario + " " : "")}${esc(a.titulo)}</button>`).join("")}</div>`;
    }
    const total = startDow + days;
    for (let i = 0; i < (7 - (total % 7)) % 7; i++) html += `<div class="day out"><span class="n">${i + 1}</span></div>`;
    $("#cal").innerHTML = html;

    $("#lista").innerHTML = rows.length
      ? `<table><thead><tr><th>Data</th><th>Atividade</th><th>Local / responsável</th><th>Situação</th><th></th></tr></thead><tbody>${rows.map((r) => `<tr>
          <td>${esc(fmtData(r.data))}<small>${esc(r.horario || "")}</small></td><td><b>${esc(r.titulo)}</b><small>${esc(lab(r.tipo))}</small></td>
          <td>${esc(r.local || "—")}<small>${esc(r.responsavel || "")}</small></td><td>${badge(r.status)}</td>
          <td class="actions"><button class="btn small" data-act="edit" data-id="${esc(r.id)}">Editar</button>${IS_ADMIN ? `<button class="btn small danger" data-act="del" data-id="${esc(r.id)}">Excluir</button>` : ""}</td></tr>`).join("")}</tbody></table>`
      : `<p class="empty">Nenhuma atividade neste mês.</p>`;
  }

  const edit = (row) => openForm({ title: `Editar — ${row.titulo}`, fields: fields(), values: row,
    onSubmit: async (d) => { await api("PUT", `/api/atividades/${row.id}`, d); toast("Alterações salvas."); load(); } }).catch(fail);
  const create = (date) => openForm({ title: "Nova atividade", fields: fields(), values: { data: date || isoToday(), status: "planejada", tipo: "feira_adocao" },
    onSubmit: async (d) => { await api("POST", "/api/atividades", d); toast("Atividade criada."); load(); } }).catch(fail);

  $("#btn-new").addEventListener("click", () => create());
  $("#prev").addEventListener("click", () => { cur = cur.m === 0 ? { y: cur.y - 1, m: 11 } : { y: cur.y, m: cur.m - 1 }; load(); });
  $("#next").addEventListener("click", () => { cur = cur.m === 11 ? { y: cur.y + 1, m: 0 } : { y: cur.y, m: cur.m + 1 }; load(); });
  $("#hoje").addEventListener("click", () => { cur = { y: now.getFullYear(), m: now.getMonth() }; load(); });
  root.addEventListener("click", async (e) => {
    const chip = e.target.closest(".chip"), btn = e.target.closest("button[data-act]"), day = e.target.closest(".day[data-date]");
    const id = (chip || btn)?.dataset.id, row = rows.find((r) => r.id === id);
    if (btn && row && btn.dataset.act === "edit") return edit(row);
    if (btn && row && btn.dataset.act === "del") {
      if (await confirmBox(`Excluir "${row.titulo}"?`)) { try { await api("DELETE", `/api/atividades/${row.id}`); toast("Atividade excluída."); load(); } catch (err) { fail(err); } }
      return;
    }
    if (chip && row) return edit(row);
    if (day) create(day.dataset.date);
  });
  load();
}

/* ============================ Relatórios ============================ */
function pageRelatorios() {
  const root = $("#app");
  const hoje = new Date(), ini = new Date(hoje.getFullYear(), hoje.getMonth() - 11, 1);
  const iso = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  root.innerHTML = `
    <div class="page-head"><div><h1>Relatórios</h1><p class="sub">Acompanhe a evolução das atividades da ONG ao longo do tempo.</p></div></div>
    <form class="filters card" id="filtros">
      <label class="field"><span>De</span><input type="date" name="de" value="${iso(ini)}"></label>
      <label class="field"><span>Até</span><input type="date" name="ate" value="${iso(hoje)}"></label>
      <button class="btn primary" type="submit">Atualizar</button>
      <span class="spacer"></span>
      <a class="btn" id="csv-ado" href="#" download>⭳ Adoções (CSV)</a>
      <a class="btn" href="/api/export/animais.csv" download>⭳ Animais (CSV)</a>
      ${IS_ADMIN ? `<a class="btn" href="/api/export/adotantes.csv" download>⭳ Adotantes (CSV)</a>` : ""}
    </form>
    <div id="rel"><p class="loading">Carregando…</p></div>`;

  async function load() {
    const fd = new FormData($("#filtros")), qs = new URLSearchParams({ de: fd.get("de"), ate: fd.get("ate") });
    $("#csv-ado").href = `/api/export/adocoes.csv?${qs}`;
    let d;
    try { d = await api("GET", `/api/relatorios/adocoes?${qs}`); } catch (e) { $("#rel").innerHTML = ""; return fail(e); }
    $("#rel").innerHTML = `
      <div class="stats">
        <div class="stat accent"><b>${fmtNum(d.total_adocoes)}</b><span>Adoções no período</span></div>
        <div class="stat"><b>${fmtNum(d.total_cadastros)}</b><span>Animais cadastrados</span></div>
        <div class="stat warm"><b>${d.tempo_medio_dias === null ? "—" : fmtNum(d.tempo_medio_dias, 0) + " dias"}</b><span>Tempo médio até a adoção</span></div>
        <div class="stat"><b>${fmtNum(d.cidades_distintas)}</b><span>Cidades de adotantes</span></div>
      </div>
      <section class="card"><h2>Cadastros e adoções por mês</h2><div id="g-mes"></div></section>
      <div class="grid-2 pad-top"><section class="card"><h2>Adoções por espécie</h2><div id="g-esp"></div></section>
        <section class="card"><h2>Principais cidades dos adotantes</h2><div id="g-cid"></div></section></div>`;
    barChart($("#g-mes"), d.por_mes.meses, [{ name: "Animais cadastrados", values: d.por_mes.cadastros }, { name: "Adoções", values: d.por_mes.adocoes }]);
    hBars($("#g-esp"), d.por_especie, lab);
    hBars($("#g-cid"), d.por_cidade);
  }
  $("#filtros").addEventListener("submit", (e) => { e.preventDefault(); load(); });
  load();
}

/* ============================ Previsão ============================ */
function pagePrevisao() {
  const root = $("#app");
  root.innerHTML = `
    <div class="page-head"><div><h1>Previsão de cadastros</h1>
      <p class="sub">Estimativa do número de animais novos que a ONG deve cadastrar nos próximos meses, calculada a partir do histórico.</p></div></div>
    <form class="card controls" id="ctl">
      <label class="field"><span>Horizonte</span><select name="meses">
        ${[3, 6, 9, 12].map((n) => `<option value="${n}" ${n === 6 ? "selected" : ""}>Próximos ${n} meses</option>`).join("")}</select></label>
      <button class="btn primary" type="submit" id="go">Gerar previsão</button>
      <p class="hint">A previsão é calculada sob demanda, com os dados atuais do sistema.</p>
    </form>
    <div id="out"></div>`;

  $("#ctl").addEventListener("submit", async (e) => {
    e.preventDefault();
    const btn = $("#go"), out = $("#out");
    btn.disabled = true; btn.textContent = "Calculando…";
    try {
      const d = await api("GET", `/api/previsao?meses=${new FormData(e.target).get("meses")}`);
      const m = d.metricas;
      const delta = d.media_historica_12m ? Math.round(((d.media_prevista - d.media_historica_12m) / d.media_historica_12m) * 100) : null;
      out.innerHTML = `
        <div class="stats pad-top">
          <div class="stat accent"><b>${fmtNum(d.total_previsto)}</b><span>Cadastros previstos no período</span></div>
          <div class="stat"><b>${fmtNum(d.media_prevista, 1)}</b><span>Média mensal prevista${delta === null ? "" : ` (${delta >= 0 ? "+" : ""}${delta}% vs. últimos 12 meses)`}</span></div>
          <div class="stat warm"><b>${esc(fmtMes(d.pico.mes))}</b><span>Mês de maior demanda (~${d.pico.inteiro} animais)</span></div>
          <div class="stat"><b>${fmtNum(d.meses_historico)}</b><span>Meses de histórico usados</span></div>
        </div>
        <section class="card"><h2>Histórico e estimativa</h2><div id="g"></div>
          ${d.aviso ? `<p class="forecast-note">${esc(d.aviso)}</p>` : ""}</section>
        <div class="grid-2 pad-top">
          <section class="card table-card"><div class="table-scroll"><table><thead><tr><th>Mês</th><th>Estimativa</th><th>Faixa provável (80%)</th></tr></thead><tbody>
            ${d.previsao.map((p) => `<tr><td>${esc(fmtMes(p.mes))}</td><td><b>${p.inteiro}</b></td><td>${p.minimo} a ${p.maximo}</td></tr>`).join("")}</tbody></table></div></section>
          <section class="card"><h2>Como ler e usar</h2>
            <p class="hint">${d.metodo === "media_movel" ? "Método: média móvel dos últimos 3 meses." : "Método: regressão linear com tendência e sazonalidade anual."}
            A faixa indica onde o valor real deve cair em 8 de cada 10 meses.</p>
            ${m ? `<div class="metrics pad-top"><div><b>${fmtNum(m.mae_modelo, 1)}</b><span>Erro médio do modelo (animais/mês) nos últimos ${m.meses_testados} meses</span></div>
              <div><b>${fmtNum(m.mae_referencia, 1)}</b><span>Erro médio de uma média simples</span></div>
              ${m.melhoria_pct !== null ? `<div><b>${m.melhoria_pct > 0 ? "−" : "+"}${fmtNum(Math.abs(m.melhoria_pct), 0)}%</b><span>Erro vs. média simples</span></div>` : ""}</div>`
              : `<p class="hint pad-top">Validação indisponível: são necessários ao menos 15 meses de histórico.</p>`}
            <p class="hint pad-top">Use a estimativa para planejar campanhas, ração, vagas e escalas de voluntários antes dos meses de pico.
            Trata-se de uma projeção estatística: eventos fora do padrão (resgates em massa, mudanças de política) não são previstos.</p>
          </section></div>`;
      forecastChart($("#g"), d.historico, d.previsao);
    } catch (err) { out.innerHTML = `<p class="form-error pad-top" role="alert">${esc(err.message)}</p>`; }
    finally { btn.disabled = false; btn.textContent = "Gerar previsão"; }
  });
}

/* ============================ Roteamento ============================ */
const PAGES = {
  dashboard: pageDashboard, animais: pageAnimais, adotantes: pageAdotantes, adocoes: pageAdocoes,
  atividades: pageAtividades, relatorios: pageRelatorios, previsao: pagePrevisao, usuarios: pageUsuarios,
};
(PAGES[document.body.dataset.page] || (() => {}))();
})();
