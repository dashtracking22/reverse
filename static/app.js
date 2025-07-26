document.addEventListener("DOMContentLoaded", fetchOdds);

async function fetchOdds() {
  const res = await fetch("/odds");
  const games = await res.json();

  const container = document.getElementById("gamesContainer");
  container.innerHTML = "";

  games.forEach(game => {
    const card = document.createElement("div");
    card.className = "game-card";

    const header = document.createElement("div");
    header.className = "game-header";
    header.innerHTML = `<h2>${game.matchup}</h2><span>${game.commence_time}</span>`;
    card.appendChild(header);

    const box = document.createElement("div");
    box.className = "odds-box";

    const table = document.createElement("table");
    const thead = document.createElement("thead");
    thead.innerHTML = `<tr><th>Fighter</th><th>Open</th><th>Live</th><th>Diff</th></tr>`;
    table.appendChild(thead);

    const tbody = document.createElement("tbody");
    for (const fighter in game.moneyline) {
      const { open, live, diff } = game.moneyline[fighter];
      const row = document.createElement("tr");
      row.innerHTML = `
        <td>${fighter}</td>
        <td>${open}</td>
        <td>${live}</td>
        <td class="diff ${getDiffClass(diff)}">${diff}</td>
      `;
      tbody.appendChild(row);
    }

    table.appendChild(tbody);
    box.appendChild(table);
    card.appendChild(box);
    container.appendChild(card);
  });
}

function getDiffClass(diff) {
  if (typeof diff === "string") {
    if (diff.startsWith("+")) return "positive";
    if (diff.startsWith("-")) return "negative";
  }
  return "";
}
