document.addEventListener("DOMContentLoaded", () => {
  const sportSelect = document.getElementById("sport-select");
  const gamesContainer = document.getElementById("games-container");

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
    const sport = sportSelect.value;
    fetch(`/odds/${sport}`)
      .then((res) => res.json())
      .then((games) => {
        gamesContainer.innerHTML = "";
        games.forEach((game) => {
          const card = document.createElement("div");
          card.className = "card";

          const title = document.createElement("h3");
          title.textContent = `${game.matchup} — ${game.commence_time_est}`;
          card.appendChild(title);

          // Helper function
          const renderSection = (label, data) => {
            if (!data.opening) return;

            const section = document.createElement("div");
            section.className = "section";

            const header = document.createElement("h4");
            header.textContent = label;
            section.appendChild(header);

            const grid = document.createElement("div");
            grid.className = "grid";

            // Header row
            ["Team", "Open", "Live", "Diff"].forEach((col) => {
              const cell = document.createElement("div");
              cell.className = "grid-header";
              cell.textContent = col;
              grid.appendChild(cell);
            });

            Object.keys(data.opening.price || {}).forEach((team) => {
              const rowData = {
                team,
                open: "",
                live: "",
                diff: "",
              };

              if (label === "Moneyline") {
                rowData.open = data.opening.price[team];
                rowData.live = data.current.price[team];
                rowData.diff = data.diff[team] > 0
                  ? `+${data.diff[team]}`
                  : `${data.diff[team]}`;
              } else {
                const ptOpen = data.opening.points[team];
                const ptLive = data.current.points[team];
                const priceOpen = data.opening.price[team];
                const priceLive = data.current.price[team];
                const ptDiff = data.diff[team];

                rowData.open = `${ptOpen} (${priceOpen})`;
                rowData.live = `${ptLive} (${priceLive})`;
                rowData.diff = ptDiff > 0 ? `+${ptDiff}` : `${ptDiff}`;
              }

              // Team
              const teamCell = document.createElement("div");
              teamCell.className = "grid-cell";
              teamCell.textContent = rowData.team;
              grid.appendChild(teamCell);

              // Open
              const openCell = document.createElement("div");
              openCell.className = "grid-cell";
              openCell.textContent = rowData.open;
              grid.appendChild(openCell);

              // Live
              const liveCell = document.createElement("div");
              liveCell.className = "grid-cell";
              liveCell.textContent = rowData.live;
              grid.appendChild(liveCell);

              // Diff
              const diffCell = document.createElement("div");
              diffCell.className = "grid-cell";
              diffCell.textContent = rowData.diff;
              diffCell.className +=
                parseFloat(rowData.diff) > 0
                  ? " diff-positive"
                  : parseFloat(rowData.diff) < 0
                  ? " diff-negative"
                  : "";
              grid.appendChild(diffCell);
            });

            section.appendChild(grid);
            card.appendChild(section);
          };

          renderSection("Moneyline", game.moneyline);
          renderSection("Spread", game.spread);
          renderSection("Total", game.total);

          gamesContainer.appendChild(card);
        });
      })
      .catch((err) => {
        console.error("Error loading odds:", err);
        gamesContainer.innerHTML = `<p>Error loading data. Please try again later.</p>`;
      });
  });
});
