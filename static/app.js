const baseURL = "";

document.addEventListener("DOMContentLoaded", () => {
  loadSports();
  document.getElementById("sportSelect").addEventListener("change", fetchOdds);
  document.getElementById("bookmakerSelect").addEventListener("change", fetchOdds);
});

async function loadSports() {
  const res = await fetch(`${baseURL}/sports`);
  const sports = await res.json();

  const sportSelect = document.getElementById("sportSelect");
  sportSelect.innerHTML = "";

  sports.forEach(sport => {
    const option = document.createElement("option");
    option.value = sport.key;
    option.textContent = sport.title;
    sportSelect.appendChild(option);
  });

  if (sports.length > 0) {
    sportSelect.value = sports[0].key;
    fetchOdds();
  }
}

async function fetchOdds() {
  const sportSelect = document.getElementById("sportSelect");
  const bookmakerSelect = document.getElementById("bookmakerSelect");
  const spinner = document.getElementById("loadingSpinner");
  const sportKey = sportSelect.value;
  const bookmaker = bookmakerSelect.value;

  spinner.style.display = "block";
  sportSelect.disabled = true;
  bookmakerSelect.disabled = true;

  try {
    const res = await fetch(`${baseURL}/odds/${sportKey}?bookmaker=${bookmaker}`);
    const games = await res.json();

    if (!Array.isArray(games)) {
      throw new Error("Failed to load odds");
    }

    renderGames(games);
  } catch (e) {
    console.error(e);
    document.getElementById("gamesContainer").innerHTML = "<p style='color:red;'>Failed to load odds.</p>";
  } finally {
    spinner.style.display = "none";
    sportSelect.disabled = false;
    bookmakerSelect.disabled = false;
  }
}

function renderGames(games) {
  const container = document.getElementById("gamesContainer");
  container.innerHTML = "";

  games.forEach(game => {
    const card = document.createElement("div");
    card.className = "game-card";

    const header = document.createElement("div");
    header.className = "game-header";
    header.innerHTML = `
      <h2>${game.matchup}</h2>
      <span>${game.commence_time}</span>
    `;
    card.appendChild(header);

    renderSection(card, "Moneyline", game.moneyline);
    renderSection(card, "Spread", game.spread);
    renderSection(card, "Total", game.total);

    container.appendChild(card);
  });
}

function renderSection(card, label, data) {
  if (!data || Object.keys(data).length === 0) return;

  const box = document.createElement("div");
  box.className = "odds-box";

  const title = document.createElement("h3");
  title.textContent = label;
  box.appendChild(title);

  const grid = document.createElement("div");
  grid.className = "odds-grid";

  const headerRow = document.createElement("div");
  headerRow.className = "odds-row header";
  headerRow.innerHTML = `
    <div>Team</div>
    <div>Open</div>
    <div>Live</div>
    <div>Diff</div>
  `;
  grid.appendChild(headerRow);

  for (const team in data) {
    const { open, live, diff } = data[team];
    const row = document.createElement("div");
    row.className = "odds-row";
    row.innerHTML = `
      <div>${team}</div>
      <div>${open}</div>
      <div>${live}</div>
      <div class="diff ${getDiffClass(diff)}">${diff}</div>
    `;
    grid.appendChild(row);
  }

  box.appendChild(grid);
  card.appendChild(box);
}

function getDiffClass(diff) {
  if (typeof diff === "string") {
    if (diff.startsWith("+")) return "positive";
    if (diff.startsWith("-")) return "negative";
  }
  return "";
}
