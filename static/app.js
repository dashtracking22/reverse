const API_BASE = "https://reversetracking.onrender.com";

// Fallbacks in case /sports or /bookmakers fail
const FALLBACK_SPORTS = [
  { key: "americanfootball_ncaaf", title: "NCAAF" },
  { key: "americanfootball_nfl", title: "NFL" },
  { key: "baseball_mlb", title: "MLB" },
  { key: "basketball_nba", title: "NBA" },
  { key: "basketball_wnba", title: "WNBA" },
  { key: "mma_mixed_martial_arts", title: "MMA" }
];

const FALLBACK_BOOKMAKERS = [
  { key: "betonlineag", title: "BetOnlineAG" },
  { key: "draftkings", title: "DraftKings" },
  { key: "fanduel", title: "FanDuel" }
];

const sportSelect = document.getElementById("sportSelect");
const bookmakerSelect = document.getElementById("bookmakerSelect");
const refreshBtn = document.getElementById("refreshBtn");
const content = document.getElementById("content");

async function fetchSports() {
  try {
    const res = await fetch(`${API_BASE}/sports`);
    if (!res.ok) throw new Error(`Sports API error: ${res.status}`);
    const sports = await res.json();
    populateSports(sports);
  } catch (err) {
    console.error("Failed to load sports from API, using fallback:", err);
    populateSports(FALLBACK_SPORTS);
  }
}

function populateSports(sports) {
  sportSelect.innerHTML = "";
  sports.forEach(sport => {
    const opt = document.createElement("option");
    opt.value = sport.key;
    opt.textContent = sport.title;
    sportSelect.appendChild(opt);
  });
}

async function fetchBookmakers() {
  try {
    const res = await fetch(`${API_BASE}/bookmakers`);
    if (!res.ok) throw new Error(`Bookmakers API error: ${res.status}`);
    const bookmakers = await res.json();
    populateBookmakers(bookmakers);
  } catch (err) {
    console.error("Failed to load bookmakers from API, using fallback:", err);
    populateBookmakers(FALLBACK_BOOKMAKERS);
  }
}

function populateBookmakers(bookmakers) {
  bookmakerSelect.innerHTML = "";
  bookmakers.forEach(bm => {
    const opt = document.createElement("option");
    opt.value = bm.key;
    opt.textContent = bm.title;
    bookmakerSelect.appendChild(opt);
  });
}

async function fetchOdds() {
  const sport = sportSelect.value;
  const bookmaker = bookmakerSelect.value;

  if (!sport || !bookmaker) {
    console.warn("Sport or bookmaker not selected.");
    return;
  }

  try {
    const res = await fetch(`${API_BASE}/odds/${sport}?bookmaker=${bookmaker}`);
    if (!res.ok) throw new Error(`Odds API error: ${res.status}`);
    const data = await res.json();
    renderOdds(data);
  } catch (err) {
    console.error("Failed to load odds:", err);
    content.innerHTML = `<p class="error">Failed to load odds. Check console.</p>`;
  }
}

function renderOdds(data) {
  if (!data || !data.length) {
    content.innerHTML = "<p>No games available.</p>";
    return;
  }

  let html = "";
  data.forEach(game => {
    html += `
      <div class="game-card">
        <h3>${game.commence_time} — ${game.home_team} vs ${game.away_team}</h3>
        ${renderMarket("Moneyline", game.markets.moneyline)}
        ${renderMarket("Spread", game.markets.spread)}
        ${renderMarket("Total", game.markets.total)}
      </div>
    `;
  });
  content.innerHTML = html;
}

function renderMarket(title, market) {
  if (!market || !market.length) return "";
  let rows = "";
  market.forEach(team => {
    rows += `
      <tr>
        <td>${team.name}</td>
        <td>${team.open}</td>
        <td>${team.live}</td>
        <td>${team.diff}</td>
      </tr>
    `;
  });
  return `
    <div class="market">
      <h4>${title}</h4>
      <table>
        <thead>
          <tr><th>Team</th><th>Open</th><th>Live</th><th>Diff</th></tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
    </div>
  `;
}

// Event listeners
refreshBtn.addEventListener("click", fetchOdds);
sportSelect.addEventListener("change", fetchOdds);
bookmakerSelect.addEventListener("change", fetchOdds);

// Init
fetchSports();
fetchBookmakers();
