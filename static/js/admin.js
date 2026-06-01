/* Investor Index — admin / control room */
(() => {
  const $ = (s, r = document) => r.querySelector(s);
  const esc = s => (s || "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

  /* theme */
  const tk = "ii-theme";
  function applyTheme(t) { document.documentElement.setAttribute("data-theme", t); localStorage.setItem(tk, t); $("#themeToggle").textContent = t === "dark" ? "☀" : "☾"; }
  $("#themeToggle").onclick = () => applyTheme(document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark");
  applyTheme(localStorage.getItem(tk) || "dark");

  function toast(m) { const t = $("#toast"); t.textContent = m; t.classList.add("show"); setTimeout(() => t.classList.remove("show"), 2400); }
  const photoCell = (p, n) => p ? `<img src="${p}" alt="">` : `<span class="ph">${(n || "?").charAt(0).toUpperCase()}</span>`;

  let investors = [], quarters = [], activeQuarter = null;

  async function loadAll() {
    investors = (await fetch("/api/investors").then(r => r.json())).investors || [];
    const q = await fetch("/api/quarters").then(r => r.json());
    quarters = q.quarters || []; activeQuarter = q.active_id;
    renderInvestors(); renderQuarters();
  }

  /* ---- investors ---- */
  function renderInvestors() {
    $("#investorList").innerHTML = investors.map(i => `
      <div class="list-item" data-id="${i.id}">${photoCell(i.photo, i.name)}
        <div class="grow"><b>${esc(i.name)}</b>${i.is_benchmark ? ' <span class="pill">benchmark</span>' : ""}
          <div style="font-size:12px;color:var(--text-faint)">${esc(i.tagline || "")}</div></div>
        <button class="btn ghost edit" data-id="${i.id}">edit</button>
        <button class="del" data-id="${i.id}">remove</button></div>
      <form class="edit-row" data-id="${i.id}" style="display:none;gap:8px;padding:12px 14px;margin:-4px 0 8px;border:1px solid var(--line);border-radius:10px;background:var(--surface-2)">
        <div class="field"><label>Name</label><input name="name" value="${esc(i.name)}" required></div>
        <div class="field"><label>Tagline</label><input name="tagline" value="${esc(i.tagline || "")}"></div>
        <div class="field"><label>Accent color</label><input name="color" type="color" value="${esc(i.color || "#c9a45c")}" style="width:60px;padding:2px;height:34px"></div>
        <div class="field"><label>Photo</label><input name="photo" type="file" accept="image/*"></div>
        <label style="display:flex;gap:8px;align-items:center;font-size:13px"><input name="is_benchmark" type="checkbox" ${i.is_benchmark ? "checked" : ""}> Benchmark (e.g. index)</label>
        <div style="display:flex;gap:8px"><button type="submit" class="btn gold">Save changes</button><button type="button" class="btn ghost cancel">Cancel</button></div>
      </form>`).join("") ||
      `<div style="color:var(--text-faint);font-size:13px">No competitors yet.</div>`;

    $("#investorList").querySelectorAll(".edit").forEach(b => b.onclick = () => {
      const f = $(`.edit-row[data-id="${b.dataset.id}"]`);
      f.style.display = f.style.display === "none" ? "grid" : "none";
    });
    $("#investorList").querySelectorAll(".cancel").forEach(b => b.onclick = () => {
      b.closest(".edit-row").style.display = "none";
    });
    $("#investorList").querySelectorAll(".edit-row").forEach(f => f.onsubmit = async e => {
      e.preventDefault();
      const fd = new FormData(f);
      fd.set("is_benchmark", f.is_benchmark.checked ? "1" : "0");
      if (!f.photo.files.length) fd.delete("photo");
      const r = await fetch("/api/investors/" + f.dataset.id, { method: "POST", body: fd });
      if (r.ok) { toast("Saved"); loadAll(); } else toast("Error saving");
    });
    $("#investorList").querySelectorAll(".del").forEach(b => b.onclick = async () => {
      if (!confirm("Remove this competitor and their picks?")) return;
      await fetch("/api/investors/" + b.dataset.id, { method: "DELETE" });
      toast("Removed"); loadAll();
    });
  }
  $("#investorForm").onsubmit = async e => {
    e.preventDefault();
    const r = await fetch("/api/investors", { method: "POST", body: new FormData(e.target) });
    if (r.ok) { toast("Competitor added"); e.target.reset(); loadAll(); } else toast("Error adding");
  };

  /* ---- quarters + their buy orders ---- */
  const openQuarters = new Set();   // remember which panels are expanded across re-renders

  function renderQuarters() {
    if (!quarters.length) {
      $("#quarterList").innerHTML = `<div style="color:var(--text-faint);font-size:13px">No quarters yet. Add one above.</div>`;
      return;
    }
    $("#quarterList").innerHTML = quarters.map(q => `
      <div class="list-item" data-qid="${q.id}"><div class="grow"><b>${esc(q.label)}</b>
        ${q.id === activeQuarter ? ' <span class="pill">active</span>' : ""}
        <div style="font-size:12px;color:var(--text-faint)">${esc(q.start_date)} → ${esc(q.end_date)}</div></div>
        ${q.id === activeQuarter ? "" : `<button class="btn ghost act" data-id="${q.id}">activate</button>`}
        <button class="btn ghost edit-q" data-id="${q.id}">edit</button>
        <button class="del del-q" data-id="${q.id}">remove</button></div>
      <div class="q-edit" data-qid="${q.id}" style="display:none;padding:14px;margin:-4px 0 10px;border:1px solid var(--line);border-radius:10px;background:var(--surface-2)">
        <form class="q-meta" data-qid="${q.id}" style="display:grid;gap:10px;grid-template-columns:1fr 1fr 1fr auto;align-items:end">
          <div class="field" style="margin:0"><label>Label</label><input name="label" value="${esc(q.label)}" required></div>
          <div class="field" style="margin:0"><label>Start date</label><input name="start_date" type="date" value="${esc(q.start_date)}" required></div>
          <div class="field" style="margin:0"><label>End date</label><input name="end_date" type="date" value="${esc(q.end_date)}" required></div>
          <button class="btn gold" type="submit">Save dates</button>
        </form>
        <div class="panel-head" style="margin-top:16px"><h3 style="font-size:14px">Buy orders</h3><span class="rule"></span>
          <button class="btn ghost refresh-q" data-id="${q.id}">↻ Refresh prices</button></div>
        <div style="overflow-x:auto"><table class="board"><thead><tr>
          <th class="l">Investor</th><th class="l">Ticker</th><th class="l">Yahoo symbol</th>
          <th class="l">Buy price</th><th class="l">Buy date</th><th></th>
        </tr></thead><tbody class="pos-body" data-qid="${q.id}"></tbody></table></div>
      </div>`).join("");

    $("#quarterList").querySelectorAll(".act").forEach(b => b.onclick = async () => {
      await fetch(`/api/quarters/${b.dataset.id}/activate`, { method: "POST" });
      toast("Activated"); loadAll();
    });
    $("#quarterList").querySelectorAll(".del-q").forEach(b => b.onclick = async () => {
      const q = quarters.find(x => x.id == b.dataset.id);
      if (!confirm(`Remove "${q ? q.label : "this quarter"}" and all of its buy orders? This cannot be undone.`)) return;
      const r = await fetch("/api/quarters/" + b.dataset.id, { method: "DELETE" });
      openQuarters.delete(Number(b.dataset.id));
      toast(r.ok ? "Quarter removed" : "Error removing"); loadAll();
    });
    $("#quarterList").querySelectorAll(".edit-q").forEach(b => b.onclick = () => toggleQuarter(b.dataset.id));
    $("#quarterList").querySelectorAll(".q-meta").forEach(f => f.onsubmit = async e => {
      e.preventDefault();
      const body = { label: f.label.value, start_date: f.start_date.value, end_date: f.end_date.value };
      const r = await fetch("/api/quarters/" + f.dataset.qid, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
      if (r.ok) { toast("Quarter updated"); loadAll(); } else toast("Error saving");
    });
    $("#quarterList").querySelectorAll(".refresh-q").forEach(b => b.onclick = async () => {
      b.disabled = true; b.textContent = "↻ Fetching…";
      const r = await fetch(`/api/refresh?quarter_id=${b.dataset.id}`, { method: "POST" }).then(r => r.json());
      const real = Object.values(r.report || {}).filter(x => x.kind === "real").length;
      const failed = Object.values(r.report || {}).filter(x => x.kind === "failed").length;
      toast(`Done · ${real} live${failed ? `, ${failed} unavailable` : ""}`); b.disabled = false; b.textContent = "↻ Refresh prices";
    });

    // re-open and reload any panels that were expanded before the re-render
    openQuarters.forEach(qid => {
      const panel = $(`.q-edit[data-qid="${qid}"]`);
      if (panel) { panel.style.display = "block"; loadPositions(qid); }
    });
  }

  function toggleQuarter(qid) {
    const panel = $(`.q-edit[data-qid="${qid}"]`);
    if (!panel) return;
    const show = panel.style.display === "none";
    panel.style.display = show ? "block" : "none";
    if (show) { openQuarters.add(Number(qid)); loadPositions(qid); }
    else openQuarters.delete(Number(qid));
  }

  async function loadPositions(qid) {
    const body = $(`.pos-body[data-qid="${qid}"]`); if (!body) return;
    const qtr = quarters.find(q => q.id == qid);
    const positions = (await fetch(`/api/positions?quarter_id=${qid}`).then(r => r.json())).positions || [];
    const byInv = {}; positions.forEach(p => byInv[p.investor_id] = p);
    body.innerHTML = investors.map(i => {
      const p = byInv[i.id] || {};
      return `<tr data-inv="${i.id}" data-pid="${p.id || ""}">
        <td class="l"><div class="player">${photoCell(i.photo, i.name)}<div class="nm">${esc(i.name)}</div></div></td>
        <td class="l"><input class="t-ticker" value="${esc(p.ticker || "")}" placeholder="POET" style="width:90px"></td>
        <td class="l"><input class="t-ysym" value="${esc(p.yahoo_symbol || "")}" placeholder="POET.OL" style="width:120px"></td>
        <td class="l"><input class="t-buy" type="number" step="any" value="${p.buy_price ?? ""}" placeholder="5.67" style="width:100px"></td>
        <td class="l"><input class="t-date" type="date" value="${esc(p.buy_date || (qtr?.start_date) || "")}" style="width:150px"></td>
        <td style="white-space:nowrap"><button class="btn gold save">save</button>${p.id ? ` <button class="del del-pos">remove</button>` : ""}</td></tr>`;
    }).join("");
    body.querySelectorAll(".save").forEach(btn => btn.onclick = async () => {
      const tr = btn.closest("tr"); const inv = tr.dataset.inv;
      const ticker = $(".t-ticker", tr).value.trim();
      const buy = $(".t-buy", tr).value;
      if (!ticker || !buy) { toast("Ticker + buy price required"); return; }
      const data = { investor_id: inv, quarter_id: qid, ticker, yahoo_symbol: $(".t-ysym", tr).value.trim() || ticker, buy_price: buy, buy_date: $(".t-date", tr).value };
      const r = await fetch("/api/positions", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data) });
      if (r.ok) { toast("Saved"); loadPositions(qid); } else toast("Error saving");
    });
    body.querySelectorAll(".del-pos").forEach(btn => btn.onclick = async () => {
      const tr = btn.closest("tr"); const pid = tr.dataset.pid;
      if (!pid || !confirm("Remove this buy order?")) return;
      const r = await fetch("/api/positions/" + pid, { method: "DELETE" });
      if (r.ok) { toast("Buy order removed"); loadPositions(qid); } else toast("Error removing");
    });
  }

  $("#quarterForm").onsubmit = async e => {
    e.preventDefault(); const f = e.target;
    const body = { label: f.label.value, start_date: f.start_date.value, end_date: f.end_date.value, is_active: f.is_active.checked };
    const r = await fetch("/api/quarters", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    if (r.ok) { toast("Quarter added"); f.reset(); loadAll(); } else toast("Error");
  };

  loadAll();
})();
