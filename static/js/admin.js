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
    renderInvestors(); renderQuarters(); fillPosQuarter(); loadPositions();
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

  /* ---- quarters ---- */
  function renderQuarters() {
    $("#quarterList").innerHTML = quarters.map(q => `
      <div class="list-item"><div class="grow"><b>${esc(q.label)}</b>
        ${q.id === activeQuarter ? ' <span class="pill">active</span>' : ""}
        <div style="font-size:12px;color:var(--text-faint)">${q.start_date} → ${q.end_date}</div></div>
        ${q.id === activeQuarter ? "" : `<button class="btn ghost act" data-id="${q.id}">activate</button>`}</div>`).join("") ||
      `<div style="color:var(--text-faint);font-size:13px">No quarters yet.</div>`;
    $("#quarterList").querySelectorAll(".act").forEach(b => b.onclick = async () => {
      await fetch(`/api/quarters/${b.dataset.id}/activate`, { method: "POST" });
      toast("Activated"); loadAll();
    });
  }
  $("#quarterForm").onsubmit = async e => {
    e.preventDefault(); const f = e.target;
    const body = { label: f.label.value, start_date: f.start_date.value, end_date: f.end_date.value, is_active: f.is_active.checked };
    const r = await fetch("/api/quarters", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    if (r.ok) { toast("Quarter added"); f.reset(); loadAll(); } else toast("Error");
  };

  /* ---- positions ---- */
  function fillPosQuarter() {
    const sel = $("#posQuarter"); sel.innerHTML = "";
    quarters.forEach(q => { const o = document.createElement("option"); o.value = q.id; o.textContent = q.label; if (q.id === activeQuarter) o.selected = true; sel.appendChild(o); });
    sel.onchange = loadPositions;
  }
  async function loadPositions() {
    const qid = $("#posQuarter").value; if (!qid) { $("#posBody").innerHTML = ""; return; }
    const positions = (await fetch(`/api/positions?quarter_id=${qid}`).then(r => r.json())).positions || [];
    const byInv = {}; positions.forEach(p => byInv[p.investor_id] = p);
    $("#posBody").innerHTML = investors.map(i => {
      const p = byInv[i.id] || {};
      return `<tr data-inv="${i.id}">
        <td class="l"><div class="player">${photoCell(i.photo, i.name)}<div class="nm">${esc(i.name)}</div></div></td>
        <td class="l"><input class="t-ticker" value="${esc(p.ticker || "")}" placeholder="POET" style="width:90px"></td>
        <td class="l"><input class="t-ysym" value="${esc(p.yahoo_symbol || "")}" placeholder="POET.OL" style="width:120px"></td>
        <td class="l"><input class="t-buy" type="number" step="any" value="${p.buy_price ?? ""}" placeholder="5.67" style="width:100px"></td>
        <td class="l"><input class="t-date" type="date" value="${esc(p.buy_date || (quarters.find(q=>q.id==qid)?.start_date) || "")}" style="width:150px"></td>
        <td><button class="btn gold save">save</button></td></tr>`;
    }).join("");
    $("#posBody").querySelectorAll(".save").forEach(btn => btn.onclick = async () => {
      const tr = btn.closest("tr"); const inv = tr.dataset.inv;
      const ticker = $(".t-ticker", tr).value.trim();
      const buy = $(".t-buy", tr).value;
      if (!ticker || !buy) { toast("Ticker + buy price required"); return; }
      const body = { investor_id: inv, quarter_id: qid, ticker, yahoo_symbol: $(".t-ysym", tr).value.trim() || ticker, buy_price: buy, buy_date: $(".t-date", tr).value };
      const r = await fetch("/api/positions", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
      toast(r.ok ? "Saved" : "Error saving");
    });
  }
  $("#refreshPrices").onclick = async () => {
    const b = $("#refreshPrices"); b.disabled = true; b.textContent = "↻ Fetching…";
    const qid = $("#posQuarter").value;
    const r = await fetch(`/api/refresh?quarter_id=${qid}`, { method: "POST" }).then(r => r.json());
    const real = Object.values(r.report || {}).filter(x => x.kind === "real").length;
    const failed = Object.values(r.report || {}).filter(x => x.kind === "failed").length;
    toast(`Done · ${real} live${failed ? `, ${failed} unavailable` : ""}`); b.disabled = false; b.textContent = "↻ Refresh prices";
  };

  loadAll();
})();
