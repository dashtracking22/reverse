const API_BASE = window.location.origin.replace(/\/+$/, "");

const sportSelect = document.getElementById("sportSelect");
const bookmakerSelect = document.getElementById("bookmakerSelect");
const refreshBtn = document.getElementById("refreshBtn");
const content = document.getElementById("content");

// ---- helpers ----
function isoToLocal(iso){
  if(!iso) return "";
  try{
    const d = new Date(iso);
    const opts = { month:"2-digit", day:"2-digit", hour:"2-digit", minute:"2-digit" };
    return d.toLocaleString(undefined, opts);
  }catch(e){ return ""; }
}
function signed(val){
  if(val == null || isNaN(val)) return "-";
  const n = Number(val);
  return (n > 0 ? `+${n}` : `${n}`);
}
function rowDiffClass(v){
  if (v == null || isNaN(v)) return "";
  return Number(v) >= 0 ? "diff pos" : "diff neg";
}
function fmtPriceMaybe(x){ return (x==null || x===undefined) ? "-" : x; }
function fmtPointWithPrice(point, price){
  const p = (point==null || point===undefined) ? "-" : point;
  const pr = (price==null || price===undefined) ? "-" : price;
  return `${p} (${pr})`;
}
function renderTable(title, rowsHtml){
  return `
    <div class="section">
      <h3>${title}</h3>
      <table class="table">
        <thead>
          <tr><th>Team</th><th class="num">Open</th><th class="num">Live</th><th class="num">Diff</th></tr>
        </thead>
        <tbody>
          ${rowsHtml || `<tr><td colspan="4" style="color:#6b7280">No data</td></tr>`}
        </tbody>
      </table>
    </div>
  `;
}

// ---- controls init ----
async function initControls(){
  // Sports -> expects {"sports":[...]}
  try {
    const s = await fetch(`${API_BASE}/sports`).then(r=>r.json());
    const sports = Array.isArray(s?.sports) ? s.sports : [];
    sportSelect.innerHTML = "";
    sports.forEach(key=>{
      const opt = document.createElement("option");
      opt.value = key;
      opt.textContent = key;
      sportSelect.appendChild(opt);
    });
  } catch (e) {
    console.error("Failed to load /sports", e);
  }

  // Bookmakers -> expects {"bookmakers":[...], "default":"..."}
  try {
    const b = await fetch(`${API_BASE}/bookmakers`).then(r=>r.json());
    bookmakerSelect.innerHTML = "";
    (b.bookmakers || []).forEach(key=>{
      const opt = document.createElement("option");
      opt.value = key;
      opt.textContent = key;
      bookmakerSelect.appendChild(opt);
    });
    if (b.default) bookmakerSelect.value = b.default;
  } catch (e) {
    console.error("Failed to load /bookmakers", e);
  }
}

// ---- rendering ----
function render(records){
  content.innerHTML = "";
  if(!Array.isArray(records) || !records.length){
    content.innerHTML = `<div class="game"><div class="title">No games</div></div>`;
    return;
  }

  records.forEach(rec=>{
    const matchup = `${rec.away_team || "Away"} vs ${rec.home_team || "Home"}`;
    const when = isoToLocal(rec.commence_time);

    // Moneyline rows from rec.moneyline {Team:{open,live,diff}}
    let mlRows = "";
    Object.entries(rec.moneyline || {}).forEach(([team, vals])=>{
      const d = vals?.diff;
      mlRows += `
        <tr>
          <td>${team}</td>
          <td class="num">${fmtPriceMaybe(vals?.open)}</td>
          <td class="num">${fmtPriceMaybe(vals?.live)}</td>
          <td class="num ${rowDiffClass(d)}">${d==null? "-": signed(d)}</td>
        </tr>
      `;
    });

    // Spreads rows from rec.spreads {Team:{open_point,open_price,live_point,live_price,diff_point}}
    let spRows = "";
    Object.entries(rec.spreads || {}).forEach(([team, v])=>{
      const d = v?.diff_point;
      spRows += `
        <tr>
          <td>${team}</td>
          <td class="num">${fmtPointWithPrice(v?.open_point, v?.open_price)}</td>
          <td class="num">${fmtPointWithPrice(v?.live_point, v?.live_price)}</td>
          <td class="num ${rowDiffClass(d)}">${d==null? "-": signed(d)}</td>
        </tr>
      `;
    });

    // Totals rows from rec.totals {Over:{...},Under:{...}}
    let totRows = "";
    ["Over","Under"].forEach(side=>{
      const v = (rec.totals||{})[side];
      if(!v) return;
      const d = v?.diff_point;
      totRows += `
        <tr>
          <td>${side}</td>
          <td class="num">${fmtPointWithPrice(v?.open_point, v?.open_price)}</td>
          <td class="num">${fmtPointWithPrice(v?.live_point, v?.live_price)}</td>
          <td class="num ${rowDiffClass(d)}">${d==null? "-": signed(d)}</td>
        </tr>
      `;
    });

    const gameEl = document.createElement("div");
    gameEl.className = "game";
    gameEl.innerHTML = `
      <div class="title">
        <span class="when">${when}</span> — <span>${matchup}</span>
      </div>
      ${renderTable("Moneyline", mlRows)}
      ${renderTable("Spread", spRows)}
      ${renderTable("Total", totRows)}
    `;
    content.appendChild(gameEl);
  });
}

// ---- odds loader ----
async function loadAndRender(){
  const sport = sportSelect.value;
  const bookmaker = bookmakerSelect.value;
  content.innerHTML = "";

  if(!sport){
    content.innerHTML = `<div class="game"><div class="title">Choose a sport</div></div>`;
    return;
  }

  try{
    const res = await fetch(`${API_BASE}/odds/${encodeURIComponent(sport)}?bookmaker=${encodeURIComponent(bookmaker)}`);
    if(!res.ok){
      let err = {};
      try { err = await res.json(); } catch(_) {}
      console.error("Odds fetch failed", res.status, err);
      content.innerHTML = `<div class="game"><div class="title">Error: ${err.error || res.status}</div></div>`;
      return;
    }
    const data = await res.json(); // { sport, bookmaker, records: [...] }
    render(data.records || []);
  }catch(e){
    console.error("Odds fetch exception", e);
    content.innerHTML = `<div class="game"><div class="title">Network error loading odds</div></div>`;
  }
}

// ---- bootstrap ----
(async function(){
  await initControls();
  if (sportSelect.options.length){ sportSelect.value = sportSelect.options[0].value; }
  refreshBtn.addEventListener("click", loadAndRender);
  sportSelect.addEventListener("change", loadAndRender);
  bookmakerSelect.addEventListener("change", loadAndRender);
  loadAndRender();
})();
