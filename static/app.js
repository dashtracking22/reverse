const baseURL = ""; // Leave blank for same-origin (Render-hosted)

document.addEventListener("DOMContentLoaded", () => {
  loadSports();
  document.getElementById("sportSelect").addEventListener("change", fetchOdds);
});

async function loadSports() {
  try {
    const res = await fetch(`${baseURL}/sports`);
    const sports = await res.json();

    const select = document.getElementById("sportSelect");
    select.innerHTML = "";

    sports.forEach(sport => {
      const option = document.createElement("option");
      option.value = sport.key;
      option.textContent = sport.title;
      select.appendChild(option);
    });

    if (sports.length > 0) {
      select.value = sports[0].key;
      fetchOdds();
    }
  } catch (err) {
    console.error("Failed to load sports:", err);
  }
}

async function fetchOdds() {
  const sportKey = document.getElementById("sportSelect").value;
  try {
    const res = await fetch(`${baseURL}/odds/${sportKey}`);
    const games = await res.json();
    renderGames(games);
  } catch (err) {
    console.error("Failed to fetch odds:", err);
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

    ["moneyline", "spread", "total"].forEach(section => {
      if (!game[section] || Object.keys(game[section]).length === 0) return;

      const box = document.createElement("div");
      box.className = "odds-box";

      const title = document.createElement("h3");
      title.textContent = section.charAt(0).toUpperCase() + section.slice(1);
      box.appendChild(title);

      const table = document.createElement("table");
      const thead = document.createElement("thead");
      thead.innerHTML = `<tr><th>Team</th><th>Open</th><th>Live</th><th>Diff</th></tr>`;
      table.appendChild(thead);

      const tbody = document.createElement("tbody");

      for (const team in game[section]) {
        const { open, live, diff } = game[section][team];
        const row = document.createElement("tr");

        row.innerHTML = `
          <td>${team}</td>
          <td>${open}</td>
          <td>${live}</td>
          <td class="diff ${getDiffClass(diff)}">${diff}</td>
        `;

        tbody.appendChild(row);
      }

      table.appendChild(tbody);
      box.appendChild(table);
      card.appendChild(box);
    });

    container.appendChild(card);
  });
}

function getDiffClass(diff) {
  if (typeof diff === "number") {
    if (diff > 0) return "positive";
    if (diff < 0) return "negative";
  }
  return "";
}
