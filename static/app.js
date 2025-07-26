const API = location.origin;

function renderSection(title, data) {
  if (!data.opening || !data.current) return null;
  const sec = document.createElement("div"); sec.className = "section";
  const hdr = document.createElement("div"); hdr.className = "section-title";
  hdr.textContent = title; sec.appendChild(hdr);

  const headerRow = document.createElement("div"); headerRow.className = "row header";
  headerRow.innerHTML = `<span>Team</span><span>Open</span><span>Live</span><span>Diff</span>`;
  sec.appendChild(headerRow);

  Object.keys(data.current.price).forEach(team => {
    const row = document.createElement("div"); row.className = "row";
    const op = data.opening.points[team], opO = data.opening.price[team]||"-";
    const openT = title==="Moneyline"?opO:`${op} (${opO})`;
    const cp = data.current.points[team], cpO = data.current.price[team]||"-";
    const liveT = title==="Moneyline"?cpO:`${cp} (${cpO})`;
    const d = data.diff[team]||0, cls = d>0?"diff-pos":d<0?"diff-neg":"";
    row.innerHTML = `<span>${team}</span><span>${openT}</span><span>${liveT}</span><span class="${cls}">${d>0?"+":""}${d}</span>`;
    sec.appendChild(row);
  });

  return sec;
}

function renderGame(g) {
  const card = document.createElement("div"); card.className="game-card";
  const header = document.createElement("div"); header.className="game-header";
  header.textContent=`${g.commence_time_est} — ${g.matchup}`; card.appendChild(header);

  ["moneyline","spread","total"].forEach(type => {
    const sec = renderSection(type.charAt(0).toUpperCase()+type.slice(1), g[type]);
    if (sec) card.appendChild(sec);
  });
  return card;
}

function loadBookmakers() {
  return fetch(`${API}/bookmakers`).then(r=>r.json()).then(list=>{
    const sel=document.getElementById("bookmakerSelect"); sel.innerHTML="";
    list.forEach(b=>{ 
      const o=document.createElement("option"); 
      o.value=b.key; o.textContent=b.title; 
      sel.appendChild(o);
    });
  });
}

function loadSports() {
  return fetch(`${API}/sports`).then(r=>r.json()).then(list=>{
    const sel=document.getElementById("sportSelect"); sel.innerHTML="";
    list.forEach(s=>{ 
      const o=document.createElement("option"); 
      o.value=s.key; o.textContent=s.title; 
      sel.appendChild(o);
    });
  });
}

function loadOdds() {
  const sp = document.getElementById("sportSelect").value;
  const bk = document.getElementById("bookmakerSelect").value;
  fetch(`${API}/odds/${sp}?bookmaker=${bk}`)
    .then(r=>r.json())
    .then(games=>{
      const cont = document.getElementById("gamesContainer");
      cont.innerHTML = "";
      games.forEach(g => cont.appendChild(renderGame(g)));
    });
}

document.getElementById("bookmakerSelect").addEventListener("change", loadOdds);
document.getElementById("sportSelect").addEventListener("change", loadOdds);
window.onload = () => Promise.all([loadBookmakers(), loadSports()]).then(loadOdds);
