const API_BASE = window.location.origin.replace(/\/+$/, ""); // same host/port as Flask

const sportSelect = document.getElementById("sportSelect");
const bookmakerSelect = document.getElementById("bookmakerSelect");
const refreshBtn = document.getElementById("refreshBtn");
const cardsContainer = document.getElementById("cardsContainer");

function isoToLocal(iso){
  if(!iso) return "";
  try{
    const d = new Date(iso);
    const opts = { month:"2-digit", day:"2-digit", hour:"2-digit", minute:"2-digit" };
    return d.toLocaleString(undefined, opts);
  }catch(e){ return ""; }
}

async function initControls(){
  const [sports, books] = await Promise.all([
    fetch(`${API_BASE}/sports`).then(r=>r.json()),
    fetch(`${API_BASE}/bookmakers`).then(r=>r.json())
  ]);
  // Sports
  sportSelect.innerHTML = "";
  (sports.sports || []).forEach(s=>{
    const opt = document.createElement("option");
    opt.value = s; opt.textContent = s;
    sportSelect.appendChild(opt);
  });
  // Bookmakers
  bookmakerSelect.innerHTML = "";
  (books.bookmakers || []).forEach(b=>{
    const opt = document.createElement("option");
    opt.value = b; opt.textContent = b;
    bookmakerSelect.appendChild(opt);
  });
  if(books.default){
    bookmakerSelect.value = books.default;
  }
}

function renderRecords(records){
  cardsContainer.innerHTML = "";
  if(!records || !records.length){
    cardsContainer.innerHTML = `<div class="card"><div class="card-header"><div class="matchup">No games</div></div></div>`;
    return;
  }
  records.forEach(rec=>{
    const title = `${rec.away_team || "Away"} @ ${rec.home_team || "Home"}`;
    const when = isoToLocal(rec.commence_time);

    const moneylineRows = [];
    for(const [team, vals] of Object.entries(rec.moneyline || {})){
      const diff = vals.diff;
      moneylineRows.push(`
        <div class="tr">
          <div class="team">${team}</div>
          <div class="val mono">${vals.open ?? "-"}</div>
          <div class="val mono">${vals.live ?? "-"}</div>
          <div class="diff mono ${diff == null ? "" : (diff >= 0 ? "pos":"neg")}">${diff ?? "-"}</div>
        </div>
      `);
    }

    const spreadRows = [];
    for(const [team, v] of Object.entries(rec.spreads || {})){
      const diff = v.diff_point;
      spreadRows.push(`
        <div class="tr">
          <div class="team">${team}</div>
          <div class="val mono">${v.open_point ?? "-" } (${v.open_price ?? "-"})</div>
          <div class="val mono">${v.live_point ?? "-" } (${v.live_price ?? "-"})</div>
          <div class="diff mono ${diff == null ? "" : (diff >= 0 ? "pos":"neg")}">${diff ?? "-"}</div>
        </div>
      `);
    }

    const totalRows = [];
    for(const side of ["Over","Under"]){
      const v = (rec.totals || {})[side];
      if(!v) continue;
      const diff = v.diff_point;
      totalRows.push(`
        <div class="tr">
          <div class="team">${side}</div>
          <div class="val mono">${v.open_point ?? "-" } (${v.open_price ?? "-"})</div>
          <div class="val mono">${v.live_point ?? "-" } (${v.live_price ?? "-"})</div>
          <div class="diff mono ${diff == null ? "" : (diff >= 0 ? "pos":"neg")}">${diff ?? "-"}</div>
        </div>
      `);
    }

    const card = document.createElement("div");
    card.className = "card";
    card.innerHTML = `
      <div class="card-header">
        <div class="matchup">${title}</div>
        <div class="time">${when}</div>
      </div>
      <div class="sections">
        <div class="section">
          <h4>Moneyline</h4>
          <div class="th">
            <div>Team</div><div class="val">Open</div><div class="val">Live</div><div class="val">Diff</div>
          </div>
          ${moneylineRows.join("") || `<div class="tr"><div>No data</div></div>`}
        </div>

        <div class="section">
          <h4>Spread</h4>
          <div class="th">
            <div>Team</div><div class="val">Open</div><div class="val">Live</div><div class="val">Diff</div>
          </div>
          ${spreadRows.join("") || `<div class="tr"><div>No data</div></div>`}
        </div>

        <div class="section">
          <h4>Total</h4>
          <div class="th">
            <div>Side</div><div class="val">Open</div><div class="val">Live</div><div class="val">Diff</div>
          </div>
          ${totalRows.join("") || `<div class="tr"><div>No data</div></div>`}
        </div>
      </div>
    `;
    cardsContainer.appendChild(card);
  });
}

async function loadAndRender(){
  const sport = sportSelect.value;
  const bookmaker = bookmakerSelect.value;
  cardsContainer.innerHTML = "";
  const url = `${API_BASE}/odds/${encodeURIComponent(sport)}?bookmaker=${encodeURIComponent(bookmaker)}`;
  const res = await fetch(url);
  if(!res.ok){
    const err = await res.json().catch(()=>({}));
    cardsContainer.innerHTML = `<div class="card"><div class="card-header"><div class="matchup">Error</div><div class="time"></div></div><div class="sections"><div class="section"><div>${err.error || res.status}</div></div></div></div>`;
    return;
  }
  const data = await res.json();
  renderRecords(data.records || []);
}

(async function(){
  await initControls();
  // defaults
  if (Array.from(sportSelect.options).length){
    sportSelect.value = sportSelect.options[0].value;
  }
  refreshBtn.addEventListener("click", loadAndRender);
  sportSelect.addEventListener("change", loadAndRender);
  bookmakerSelect.addEventListener("change", loadAndRender);
  loadAndRender();
})();
