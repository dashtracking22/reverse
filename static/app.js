document.addEventListener("DOMContentLoaded", () => {
  const sportSelect = document.getElementById("sport-select");
  const gamesContainer = document.getElementById("games-container");

  if (!sportSelect || !gamesContainer) {
    console.error("Missing sport-select or games-container in HTML");
    return;
  }

  fetch("/sports")
    .then((res) => res.json())
    .then((sports) => {
      sports.forEach((sport) => {
        const option = document.createElement("option");
        option.value = sport.key;
        option.textContent = sport.title;
        sportSelect.appendChild(option);
      });
    });

  sportSelect.addEventListener("change", () => {
    const selected = sportSelect.value;
    if (!selected) return;

    fetch(`/odds/${selected}?bookmaker=betonlineag`)
      .then((res) => res.json())
      .then((games) => {
        gamesContainer.innerHTML = "";

        games.forEach((game) => {
          const card = document.createElement("div");
          card.className = "game-card";

          const header = document.createElement("h2");
          header.textContent = `${game.matchup} — ${game.commence_time_est}`;
          card.appendChild(header);

          ["moneyline", "spread", "total"].forEach((market) => {
            const section = document.createElement("div");
            section.className = "section";

            const title = document.createElement("h3");
            title.textContent = market.charAt(0).toUpperCase() + market.slice(1);
            section.appendChild(title);

            const open = game[market]?.opening || {};
            const current = game[market]?.current || {};
            const diff = game[market]?.diff || {};

            const teams = Object.keys(current.price || {});
            teams.forEach((team) => {
              const row = document.createElement("div");
              row.className = "odds-row";

              let openLine = market === "moneyline"
                ? open.price?.[team] ?? "-"
                : `${open.points?.[team] ?? "-"} (${open.price?.[team] ?? "-"})`;

              let liveLine = market === "moneyline"
                ? current.price?.[team] ?? "-"
                : `${current.points?.[team] ?? "-"} (${current.price?.[team] ?? "-"})`;

              let lineDiff = diff[team] ?? "0";
              const diffSpan = document.createElement("span");
              diffSpan.textContent = lineDiff;
              diffSpan.className = Number(lineDiff) > 0 ? "diff-positive" :
                                   Number(lineDiff) < 0 ? "diff-negative" : "";

              row.innerHTML = `
                <span>${team}</span>
                <span>Open: ${openLine}</span>
                <span>Live: ${liveLine}</span>
              `;
              row.appendChild(diffSpan);

              section.appendChild(row);
            });

            card.appendChild(section);
          });

          gamesContainer.appendChild(card);
        });
      });
  });
});
