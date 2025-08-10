const API_BASE = window.location.origin.replace(/\/+$/, "");

const sportSelect = document.getElementById("sportSelect");
const bookmakerSelect = document.getElementById("bookmakerSelect");
const refreshBtn = document.getElementById("refreshBtn");
const content = document.getElementById("content");

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

async function initControls(){
  const [sportsResp, books] = await Promise.all([
    fetch(`${API_BASE}/sports`).then(r=>r.json()),
    fetch(`${API_BASE}/bookmakers`).then(r=>r.json())
  ]);

  // /sports returns {"sports":[...]} (our backend); tolerate raw arrays just in case
  let sportKeys = [];
  if (Array.isArray(sportsResp?.sports)) sportKeys = sportsResp.sports;
  else if (Array.isArray(sportsResp)) sportKeys = sportsResp.map(s=>s.key).filter(Boolean);

  sportSelect.innerHTML = "";
  sportKeys.forEach(s=>{
    const opt = document.createElement("option");
    opt.value = s; opt.textContent = s;
    sportSelect.appendChild(opt);
  });

  bookmakerSelect.innerHTML = "";
  (books.bookmakers || []).forEach(b=>{
    const opt = document.createElement("option");
    opt.value = b; opt.textContent = b;
    bookmakerSelect.appendChild(opt);
  });
  if(books.default){ bookmakerSelect.value = books.default; }
}

function rowDiffClass(v){
  if (v == null || isNaN(v)) return "";
  return Number(v) >= 0 ? "diff pos" : "diff neg";
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

function fmtPriceMaybe(x){ return (x==null || x===undefined) ? "-" : x; }
function fmtPointWithPrice(point, price){
  const p = (point==null || point===undefined) ? "-" : point;
  const pr = (price==null || price===undefined) ? "-" : price;
  return `${p} (${pr})`;
}

function render(records){
  content.innerHTML = "";
  if(!records || !records.length){
    content.innerHTML = `<div class="game"><div class="title">No games</div></div>`;
    return;
  }

  records.forEach(rec=>{
    const matchup = `${rec.away_team || "Away"} vs ${rec.home_team || "Home"}`;
    const when = isoToLocal(rec.commence_time);

    // Moneyline
    let mlRows = "";
    Object.entries(rec.moneyline || {}).forEach(([team, vals])=>{
      const d = vals.diff;
      mlRows += `
        <tr>
          <td>${team}</td>
          <td class="num">${fmtPriceMaybe(vals.open)}</td>
          <td class="num">${fmtPriceMaybe(vals.live)}</td>
          <td class="num ${rowDiffClass(d)}">${d==null? "-": signed(d)}</td>
        </tr>
      `;
    });

    // Spread (point diff only)
    let spRows = "";
    Object.entries(rec.spreads || {}).forEach(([team, v])=>{
      const d = v.diff_point;
      spRows += `
        <tr>
          <td>${team}</td>
          <td class="num">${fmtPointWithPrice(v.open_point, v.open_price)}</td>
          <td class="num">${fmtPointWithPrice(v.live_point, v.live_price)}</td>
          <td class="num ${rowDiffClass(d)}">${d==null? "-": signed(d)}</td>
        </tr>
      `;
    });

    // Totals (point diff only) — Over/Under rows
    let totRows = "";
    ["Over","Under"].forEach(side=>{
      const v = (rec.totals||{})[side];
      if(!v) return;
      const d = v.diff_point;
      totRows += `
        <tr>
          <td>${side}</td>
          <td class="num">${fmtPointWithPrice(v.open_point, v.open_price)}</td>
          <td class="num">${fmtPointWithPrice(v.live_point, v.live_price)}</td>
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

async function loadAndRender(){
  const sport = sportSelect.value;
  const bookmaker = bookmakerSelect.value;
  content.innerHTML = "";

  if(!sport){
    content.innerHTML = `<div class="game"><div class="title">Choose a sport</div></div>`;
    return;
  }

  const url = `${API_BASE}/odds/${encodeURIComponent(sport)}?bookmaker=${encodeURIComponent(bookmaker)}`;
  const res = await fetch(url);
  if(!res.ok){
    const err = await res.json().catch(()=>({}));
    content.innerHTML = `<div class="game"><div class="title">Error: ${err.error || res.status}</div></div>`;
    return;
  }
  const data = await res.json();
  render(data.records || []);
}

(async function(){
  await initControls();
  if (sportSelect.options.length){ sportSelect.value = sportSelect.options[0].value; }
  refreshBtn.addEventListener("click", loadAndRender);
  sportSelect.addEventListener("change", loadAndRender);
  bookmakerSelect.addEventListener("change", loadAndRender);
  loadAndRender();
})();
