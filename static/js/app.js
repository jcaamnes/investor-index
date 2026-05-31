/* Investor Index — dashboard logic */
(() => {
  const $ = (s, r = document) => r.querySelector(s);
  const fmtPct = v => (v == null ? "—" : (v >= 0 ? "+" : "") + v.toFixed(2) + "%");
  const fmtNum = v => (v == null ? "—" : v.toLocaleString(undefined, { maximumFractionDigits: 2 }));
  const cls = v => (v == null ? "" : v >= 0 ? "pos" : "neg");
  const esc = s => (s || "").replace(/[&<>]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));

  let chart = null;
  let hidden = new Set();        // hidden series labels
  let currentData = null;

  /* ---- theme ---- */
  const themeKey = "ii-theme";
  function applyTheme(t) {
    document.documentElement.setAttribute("data-theme", t);
    localStorage.setItem(themeKey, t);
    $("#themeToggle").textContent = t === "dark" ? "☀" : "☾";
    if (currentData) renderChart(currentData);   // recolor grid
  }
  $("#themeToggle").addEventListener("click", () => {
    const cur = document.documentElement.getAttribute("data-theme");
    applyTheme(cur === "dark" ? "light" : "dark");
  });
  applyTheme(localStorage.getItem(themeKey) || "dark");

  function toast(msg) {
    const t = $("#toast"); t.textContent = msg; t.classList.add("show");
    setTimeout(() => t.classList.remove("show"), 2600);
  }

  function photoOrInitial(photo, name, sizeClass = "") {
    if (photo) return `<img class="${sizeClass}" src="${photo}" alt="">`;
    const i = (name || "?").trim().charAt(0).toUpperCase();
    return `<span class="ph ${sizeClass}">${i}</span>`;
  }

  /* ---- sparkline ---- */
  function sparkline(series, color) {
    const pts = series.filter(v => v != null);
    if (pts.length < 2) return "";
    const w = 96, h = 30, pad = 2;
    const min = Math.min(...pts), max = Math.max(...pts);
    const span = (max - min) || 1;
    const step = (w - pad * 2) / (pts.length - 1);
    const d = pts.map((v, i) =>
      `${i === 0 ? "M" : "L"}${(pad + i * step).toFixed(1)},${(h - pad - ((v - min) / span) * (h - pad * 2)).toFixed(1)}`
    ).join(" ");
    const last = pts[pts.length - 1];
    const lc = last >= 0 ? "var(--pos)" : "var(--neg)";
    return `<svg class="spark" viewBox="0 0 ${w} ${h}"><path d="${d}" fill="none" stroke="${color || lc}" stroke-width="1.6" stroke-linejoin="round"/></svg>`;
  }

  /* ---- data load ---- */
  async function loadQuarters() {
    const r = await fetch("/api/quarters").then(r => r.json());
    const sel = $("#quarterSelect");
    sel.innerHTML = "";
    (r.quarters || []).forEach(q => {
      const o = document.createElement("option");
      o.value = q.id; o.textContent = q.label;
      if (q.id === r.active_id) o.selected = true;
      sel.appendChild(o);
    });
    sel.onchange = () => loadDashboard(sel.value);
    return sel.value;
  }

  async function loadDashboard(qid) {
    $("#hero").innerHTML = `<div class="loading">Tallying the books…</div>`;
    const url = "/api/dashboard" + (qid ? `?quarter_id=${qid}` : "");
    const data = await fetch(url).then(r => r.json());
    if (data.error || !data.has_data) {
      $("#hero").innerHTML = `<div class="empty">No price data yet. Add competitors in “Manage”, then hit Refresh.</div>`;
      ["legend", "boardBody", "awards", "weeks", "hofBody", "hofRecords"].forEach(id => $("#" + id).innerHTML = "");
      if (chart) { chart.destroy(); chart = null; }
      return;
    }
    currentData = data;
    $("#quarterTag").textContent = "— " + data.quarter.label + " —";
    $("#genTag").textContent = "synced " + (data.generated_at || "").replace("T", " ");
    $("#synthBanner").style.display = data.is_synthetic ? "inline-block" : "none";
    renderHero(data);
    renderChart(data);
    renderLegend(data);
    renderBoard(data);
    renderAwards(data);
    renderWeeks(data.summaries || []);
    renderHOF(data.hall_of_fame || {});
  }

  /* ---- hero ---- */
  function renderHero(d) {
    const leader = d.competitors[0];
    const a = d.awards || {};
    const bench = (d.benchmarks || [])[0];
    const mini = (label, who) => who ? `
      <div class="mini"><span class="k">${label}</span>
        <span class="v">${photoOrInitial(who.photo, who.name)} ${esc(who.name)}
          <span class="${cls(who.value)}">${fmtPct(who.value)}</span></span></div>` :
      `<div class="mini"><span class="k">${label}</span><span class="v">—</span></div>`;

    $("#hero").innerHTML = `
      <div class="leader-card">
        <div>${photoOrInitial(leader.photo, leader.name, "leader-photo")}</div>
        <div class="leader-meta">
          <div class="crown">★ Best Investor · ${esc(d.quarter.label)}</div>
          <h2>${esc(leader.name)}</h2>
          <div class="tag">${esc(leader.tagline || "")}</div>
          <div class="leader-return ${cls(leader.return_pct)}">${fmtPct(leader.return_pct)}
            <span class="ticker-chip">${esc(leader.ticker)}</span></div>
        </div>
      </div>
      <div class="side-stats">
        ${mini("Biggest Loser", a.biggest_loser)}
        ${mini("Most Volatile", a.most_risky)}
        ${bench ? `<div class="mini"><span class="k">Benchmark · ${esc(bench.ticker)}</span>
            <span class="v ${cls(bench.return_pct)}">${fmtPct(bench.return_pct)}</span></div>` :
          mini("Comeback King", a.comeback_king)}
      </div>`;
  }

  /* ---- chart ---- */
  function gridColor() {
    return getComputedStyle(document.documentElement).getPropertyValue("--grid-line").trim() || "rgba(255,255,255,.05)";
  }
  function textColor() {
    return getComputedStyle(document.documentElement).getPropertyValue("--text-faint").trim() || "#888";
  }
  function renderChart(d) {
    const ctx = $("#perfChart");
    const labels = d.dates.map(x => x.slice(5)); // MM-DD
    const datasets = d.all_records.map(r => ({
      label: r.ticker,
      _name: r.name,
      _bench: !!r.is_benchmark,
      data: r.return_series,
      borderColor: r.color || "#888",
      backgroundColor: r.color || "#888",
      borderWidth: r.is_benchmark ? 1.5 : 2,
      borderDash: r.is_benchmark ? [5, 4] : [],
      pointRadius: 0, pointHoverRadius: 4, tension: 0.25, spanGaps: true,
      hidden: hidden.has(r.ticker),
    }));
    if (chart) chart.destroy();
    chart = new Chart(ctx, {
      type: "line",
      data: { labels, datasets },
      options: {
        responsive: true, maintainAspectRatio: false,
        interaction: { mode: "index", intersect: false },
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              title: items => d.dates[items[0].dataIndex],
              label: c => `${c.dataset._name} (${c.dataset.label}): ${fmtPct(c.parsed.y)}`,
            },
            itemSort: (a, b) => b.parsed.y - a.parsed.y,
          },
        },
        scales: {
          x: { grid: { color: gridColor() }, ticks: { color: textColor(), maxTicksLimit: 12 } },
          y: { grid: { color: gridColor() }, ticks: { color: textColor(), callback: v => v + "%" } },
        },
      },
    });
  }
  function renderLegend(d) {
    $("#legend").innerHTML = d.all_records.map(r => `
      <span class="legend-chip ${hidden.has(r.ticker) ? "off" : ""}" data-t="${esc(r.ticker)}">
        <span class="dot" style="background:${r.color || "#888"}"></span>
        ${esc(r.ticker)} · ${esc(r.name)}${r.is_benchmark ? " (bm)" : ""}
      </span>`).join("");
    $("#legend").querySelectorAll(".legend-chip").forEach(chip => {
      chip.onclick = () => {
        const t = chip.dataset.t;
        if (hidden.has(t)) hidden.delete(t); else hidden.add(t);
        renderChart(currentData); chip.classList.toggle("off");
      };
    });
  }

  /* ---- leaderboard ---- */
  function renderBoard(d) {
    $("#boardBody").innerHTML = d.competitors.map(r => {
      const rb = r.rank <= 3 ? `rankbadge r${r.rank}` : "rankbadge";
      return `<tr>
        <td class="l"><span class="${rb}">${r.rank}</span></td>
        <td class="l"><div class="player">${photoOrInitial(r.photo, r.name)}
          <div><div class="nm">${esc(r.name)}</div><div class="tg">${esc(r.tagline || "")}</div></div></div></td>
        <td class="l"><span class="ticker-chip">${esc(r.ticker)}</span></td>
        <td>${fmtNum(r.buy_price)}</td>
        <td>${fmtNum(r.last_close)}</td>
        <td class="${cls(r.return_pct)}">${fmtPct(r.return_pct)}</td>
        <td>${sparkline(r.return_series, r.color)}</td>
        <td class="${cls(r.gap_to_leader)}">${r.rank === 1 ? "—" : fmtPct(r.gap_to_leader)}</td>
        <td><span class="pill">${r.days_at_top}${r.lead_streak > 1 ? " 🔥" + r.lead_streak : ""}</span></td>
        <td>${r.volatility.toFixed(0)}%</td>
      </tr>`;
    }).join("");
  }

  /* ---- awards ---- */
  const AWARD_DEFS = [
    ["most_risky", "Most Risky", "🎢", v => v.toFixed(0) + "% vol", "Lives on the edge — highest annualised volatility."],
    ["biggest_loser", "Biggest Loser", "📉", fmtPct, "Currently furthest in the red."],
    ["comeback_king", "Comeback King", "🚀", v => "+" + v.toFixed(1) + "%", "Biggest rise from their lowest point."],
    ["best_risk_adj", "Smartest Money", "🧠", v => v.toFixed(2) + " Sharpe", "Best return per unit of risk."],
    ["steadiest", "Iron Nerves", "🪨", v => v.toFixed(0) + "% vol", "Calmest ride — lowest volatility."],
    ["deepest_dip", "Deepest Dip", "🕳️", fmtPct, "Largest peak-to-trough drawdown."],
    ["best_single_day", "Best Single Day", "🌟", fmtPct, "Biggest one-day pop."],
    ["worst_single_day", "Worst Single Day", "💀", fmtPct, "Ugliest one-day drop."],
    ["most_days_at_top", "Most Days at #1", "👑", v => v + " days", "Longest time owning the top spot."],
    ["biggest_climber", "Mover of the Week", "📈", v => (v >= 0 ? "+" : "") + v + " spots", "Biggest 7-day rank jump."],
  ];
  function renderAwards(d) {
    const a = d.awards || {};
    $("#awards").innerHTML = AWARD_DEFS.map(([key, title, emoji, fmt, desc]) => {
      const w = a[key];
      if (!w) return "";
      return `<div class="award"><span class="emoji">${emoji}</span>
        <div class="ttl">${title}</div>
        <div class="who">${photoOrInitial(w.photo, w.name)}<span class="nm">${esc(w.name)}</span></div>
        <div class="val">${fmt(w.value)} <span class="ticker-chip">${esc(w.ticker)}</span></div>
        <div class="desc">${desc}</div></div>`;
    }).join("");
  }

  /* ---- weekly ---- */
  function renderWeeks(weeks) {
    if (!weeks.length) { $("#weeks").innerHTML = `<div class="empty">Summaries appear once a week of trading is in the books.</div>`; return; }
    $("#weeks").innerHTML = weeks.map(w => `
      <div class="week">
        <div class="meta"><div class="wl">${esc(w.week_label)}</div><div class="dr">${esc(w.date_range)}</div></div>
        <div class="body">${esc(w.narrative)}</div>
      </div>`).join("");
  }

  /* ---- hall of fame ---- */
  function renderHOF(h) {
    const bq = h.best_quarter, wq = h.worst_quarter;
    $("#hofRecords").innerHTML = `
      <div class="record-card"><div class="lab">🏆 Best Quarter Ever</div>
        <div class="big">${bq ? esc(bq.name) + " · " + fmtPct(bq.return_pct) : "—"}</div>
        <div class="meta2">${bq ? esc(bq.ticker) + " · " + esc(bq.quarter) : ""}</div></div>
      <div class="record-card"><div class="lab">🥶 Worst Quarter Ever</div>
        <div class="big">${wq ? esc(wq.name) + " · " + fmtPct(wq.return_pct) : "—"}</div>
        <div class="meta2">${wq ? esc(wq.ticker) + " · " + esc(wq.quarter) : ""}</div></div>`;
    const rows = (h.standings || []).map(s => `<tr>
      <td class="l"><div class="player">${photoOrInitial(s.photo, s.name)}<div class="nm">${esc(s.name)}</div></div></td>
      <td>${s.quarters}</td><td>${s.wins}${s.wins ? " 🏆" : ""}</td><td>${s.podiums}</td>
      <td class="pos">${fmtPct(s.best)}</td><td class="neg">${fmtPct(s.worst)}</td>
      <td class="${cls(s.avg)}">${fmtPct(s.avg)}</td></tr>`).join("");
    $("#hofBody").innerHTML = rows || `<tr><td class="l" colspan="7"><span class="empty">No completed quarters yet.</span></td></tr>`;
  }

  /* ---- refresh ---- */
  $("#refreshBtn").addEventListener("click", async () => {
    const btn = $("#refreshBtn"); const qid = $("#quarterSelect").value;
    btn.disabled = true; btn.textContent = "↻ Fetching…";
    try {
      const r = await fetch(`/api/refresh?quarter_id=${qid}`, { method: "POST" }).then(r => r.json());
      const real = Object.values(r.report || {}).filter(x => x.kind === "real").length;
      const synth = Object.values(r.report || {}).filter(x => x.kind === "synthetic").length;
      toast(`Updated in ${r.seconds}s · ${real} live, ${synth} demo`);
      await loadDashboard(qid);
    } catch (e) { toast("Refresh failed — check your connection"); }
    btn.disabled = false; btn.textContent = "↻ Refresh";
  });

  /* ---- boot ---- */
  (async () => { const qid = await loadQuarters(); await loadDashboard(qid); })();
})();
