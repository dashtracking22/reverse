document.addEventListener("DOMContentLoaded", () => {
  const sportSelect = document.getElementById("sportSelect");
  const bookmakerSelect = document.getElementById("bookmakerSelect");
  const gamesContainer = document.getElementById("gamesContainer");

  fetch("/sports")
    .then((res) => res.json())
    .then((sports) => {
      sports.forEach((sport) => {
        const option = document.createElement("option");
        option.value = sport;
        option.textContent = sport;
        sportSelect.appendChild(option);
      });
      loadGames(sports[0], bookmakerSelect.value);
    });

  sportSelect.addEventListener("change", () => {
    loadGames(sportSelect.value, bookmakerSelect.value);
  });

  bookmakerSelect.addEventListener("change", () => {
    loadGames(sportSelect.value, bookmakerSelect.value);
  });

  function loadGames(sport, bookmaker) {
    gamesContainer.innerHTML = "Loading...";
    fetch(`/odds/${sport}?bookmaker=${bookmaker}`)
      .then((res) => res.json())
      .then((games) => {
        gamesContainer.innerHTML = "";
        games.forEach((game) => {
          const card = document.createElement("div");
          card.className = "card";

          card.innerHTML = `
            <h2>${game.matchup} — ${game.time}</h2>
            <div class="section"><h3>Moneyline</h3>${renderOddsSection(game, "moneyline")}</div>
            <div class="section"><h3>Spread</h3>${renderOddsSection(game, "spread", true)}</div>
            <div class="section"><h3>Total</h3>${renderOddsSection(game, "total", true)}</div>
          `;

          gamesContainer.appendChild(card);
        });
      });
  }

  function renderOddsSection(game, key, includePoints = false) {
    const teams = Object.keys(game[key] || {});
    return teams.map((team) => {
      const open = game.opening[key]?.[team];
      const live = game[key]?.[team];
      if (!open || !live) return "";

      let diff = "";
      if (includePoints && open.point !== undefined && live.point !== undefined) {
        const movement = (live.point - open.point).toFixed(1);
        diff = `<span class="${movement >= 0 ? "green" : "red"}">Diff: ${movement}</span>`;
      } else if (open.price && live.price) {
        const movement = live.price - open.price;
        diff = `<span class="${movement >= 0 ? "green" : "red"}">Diff: ${movement}</span>`;
      }

      return `
        <div class="row">
          <div>${team}</div>
          <div>Open: ${includePoints ? open.point + " (" + open.price + ")" : open.price}</div>
          <div>Live: ${includePoints ? live.point + " (" + live.price + ")" : live.price}</div>
          <div>${diff}</div>
        </div>
      `;
    }).join("");
  }
});
