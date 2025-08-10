document.addEventListener("DOMContentLoaded", () => {
    const sportSelect = document.getElementById("sportSelect");
    const bookmakerSelect = document.getElementById("bookmakerSelect");
    const gamesContainer = document.getElementById("gamesContainer");

    let currentSport = null;
    let currentBookmaker = null;

    async function fetchSports() {
        try {
            const res = await fetch("/sports");
            const data = await res.json();
            sportSelect.innerHTML = "";
            data.sports.forEach(sport => {
                const opt = document.createElement("option");
                opt.value = sport;
                opt.textContent = sport;
                sportSelect.appendChild(opt);
            });
            currentSport = sportSelect.value;
        } catch (err) {
            console.error("Error fetching sports:", err);
        }
    }

    async function fetchBookmakers() {
        try {
            const res = await fetch("/bookmakers");
            const data = await res.json();
            bookmakerSelect.innerHTML = "";
            data.bookmakers.forEach(bk => {
                const opt = document.createElement("option");
                opt.value = bk;
                opt.textContent = bk;
                bookmakerSelect.appendChild(opt);
            });
            bookmakerSelect.value = data.default;
            currentBookmaker = bookmakerSelect.value;
        } catch (err) {
            console.error("Error fetching bookmakers:", err);
        }
    }

    function renderGame(game) {
        const card = document.createElement("div");
        card.className = "game-card";

        const header = document.createElement("div");
        header.className = "card-header";
        const time = new Date(game.commence_time).toLocaleString();
        header.textContent = `${game.away_team} @ ${game.home_team} — ${time}`;
        card.appendChild(header);

        const table = document.createElement("table");
        table.className = "odds-table";

        const headerRow = document.createElement("tr");
        headerRow.innerHTML = `<th>Market</th><th>Team</th><th>Open</th><th>Live</th><th>Diff</th>`;
        table.appendChild(headerRow);

        const addRow = (market, team, open, live, diff) => {
            const tr = document.createElement("tr");
            tr.innerHTML = `
                <td>${market}</td>
                <td>${team}</td>
                <td>${open ?? "-"}</td>
                <td>${live ?? "-"}</td>
                <td class="${diff > 0 ? 'diff-positive' : diff < 0 ? 'diff-negative' : ''}">
                    ${diff ?? "-"}
                </td>
            `;
            table.appendChild(tr);
        };

        // Moneyline
        for (const team in game.moneyline) {
            const ml = game.moneyline[team];
            addRow("Moneyline", team, ml.open, ml.live, ml.diff);
        }
        // Spreads
        for (const team in game.spreads) {
            const sp = game.spreads[team];
            const openText = sp.open_point !== undefined ? `${sp.open_point} (${sp.open_price})` : "-";
            const liveText = sp.live_point !== undefined ? `${sp.live_point} (${sp.live_price})` : "-";
            addRow("Spread", team, openText, liveText, sp.diff_point);
        }
        // Totals
        for (const team in game.totals) {
            const to = game.totals[team];
            const openText = to.open_point !== undefined ? `${to.open_point} (${to.open_price})` : "-";
            const liveText = to.live_point !== undefined ? `${to.live_point} (${to.live_price})` : "-";
            addRow("Total", team, openText, liveText, to.diff_point);
        }

        card.appendChild(table);
        return card;
    }

    async function fetchOdds() {
        if (!currentSport || !currentBookmaker) return;
        try {
            const res = await fetch(`/odds/${currentSport}?bookmaker=${currentBookmaker}`);
            const data = await res.json();
            gamesContainer.innerHTML = "";
            if (data.records && data.records.length > 0) {
                data.records.forEach(game => {
                    gamesContainer.appendChild(renderGame(game));
                });
            } else {
                gamesContainer.textContent = "No games found.";
            }
        } catch (err) {
            console.error("Error fetching odds:", err);
            gamesContainer.textContent = "Error loading odds.";
        }
    }

    sportSelect.addEventListener("change", () => {
        currentSport = sportSelect.value;
        fetchOdds();
    });

    bookmakerSelect.addEventListener("change", () => {
        currentBookmaker = bookmakerSelect.value;
        fetchOdds();
    });

    (async function init() {
        await fetchSports();
        await fetchBookmakers();
        await fetchOdds();
    })();
});
