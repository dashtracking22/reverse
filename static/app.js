document.addEventListener("DOMContentLoaded", function () {
    const sportSelect = document.getElementById("sportSelect");
    const bookmakerSelect = document.getElementById("bookmakerSelect");
    const oddsContainer = document.getElementById("oddsContainer");

    let currentSport = null;
    let currentBookmaker = null;

    // Map API sport keys to friendly names
    const SPORT_NAMES = {
        "americanfootball_ncaaf": "NCAAF",
        "americanfootball_ncaa": "NCAAF",
        "americanfootball_nfl": "NFL",
        "basketball_nba": "NBA",
        "basketball_wnba": "WNBA",
        "mma_mixed_martial_arts": "MMA",
        "baseball_mlb": "MLB",
    };

    function friendlySportName(key) {
        return SPORT_NAMES[key] || key;
    }

    // Load sports dropdown
    fetch("/sports")
        .then((res) => res.json())
        .then((data) => {
            sportSelect.innerHTML = "";
            if (data.sports && data.sports.length > 0) {
                data.sports.forEach((key) => {
                    const opt = document.createElement("option");
                    opt.value = key;
                    opt.textContent = friendlySportName(key);
                    sportSelect.appendChild(opt);
                });
                currentSport = sportSelect.value;
            }
        })
        .catch((err) => console.error("Error loading sports:", err));

    // Load bookmakers dropdown
    fetch("/bookmakers")
        .then((res) => res.json())
        .then((data) => {
            bookmakerSelect.innerHTML = "";
            if (data.bookmakers && data.bookmakers.length > 0) {
                data.bookmakers.forEach((bk) => {
                    const opt = document.createElement("option");
                    opt.value = bk;
                    opt.textContent = bk;
                    bookmakerSelect.appendChild(opt);
                });
                if (data.default) {
                    bookmakerSelect.value = data.default;
                }
                currentBookmaker = bookmakerSelect.value;
            }
        })
        .catch((err) => console.error("Error loading bookmakers:", err));

    // Handle changes
    sportSelect.addEventListener("change", () => {
        currentSport = sportSelect.value;
        loadOdds();
    });

    bookmakerSelect.addEventListener("change", () => {
        currentBookmaker = bookmakerSelect.value;
        loadOdds();
    });

    // Load odds
    function loadOdds() {
        if (!currentSport || !currentBookmaker) return;
        oddsContainer.innerHTML = `<p>Loading odds for ${friendlySportName(currentSport)} (${currentBookmaker})...</p>`;
        fetch(`/odds/${currentSport}?bookmaker=${currentBookmaker}`)
            .then((res) => res.json())
            .then((data) => {
                if (!data.records || data.records.length === 0) {
                    oddsContainer.innerHTML = `<p>No games found for ${friendlySportName(currentSport)}</p>`;
                    return;
                }
                renderOdds(data.records);
            })
            .catch((err) => {
                console.error("Error loading odds:", err);
                oddsContainer.innerHTML = `<p>Error loading odds</p>`;
            });
    }

    // Render odds
    function renderOdds(records) {
        oddsContainer.innerHTML = "";
        records.forEach((game) => {
            const card = document.createElement("div");
            card.className = "game-card";

            const header = document.createElement("h3");
            const date = new Date(game.commence_time);
            header.textContent = `${game.away_team} @ ${game.home_team} - ${date.toLocaleString()}`;
            card.appendChild(header);

            // Moneyline section
            const mlSection = createMarketSection("Moneyline", game.moneyline, "price");
            card.appendChild(mlSection);

            // Spread section
            const spreadSection = createMarketSection("Spread", game.spreads, "point");
            card.appendChild(spreadSection);

            // Total section
            const totalSection = createMarketSection("Total", game.totals, "point");
            card.appendChild(totalSection);

            oddsContainer.appendChild(card);
        });
    }

    function createMarketSection(title, marketData, diffType) {
        const section = document.createElement("div");
        section.className = "market-section";
        const h4 = document.createElement("h4");
        h4.textContent = title;
        section.appendChild(h4);

        for (const team in marketData) {
            const row = document.createElement("div");
            row.className = "market-row";

            const tName = document.createElement("span");
            tName.textContent = team;
            row.appendChild(tName);

            if (diffType === "price") {
                row.appendChild(makeCell(marketData[team].open));
                row.appendChild(makeCell(marketData[team].live));
                row.appendChild(makeDiffCell(marketData[team].diff));
            } else {
                const md = marketData[team];
                row.appendChild(makeCell(`${md.open_point ?? ""} (${md.open_price ?? ""})`));
                row.appendChild(makeCell(`${md.live_point ?? ""} (${md.live_price ?? ""})`));
                row.appendChild(makeDiffCell(md.diff_point));
            }
            section.appendChild(row);
        }
        return section;
    }

    function makeCell(val) {
        const span = document.createElement("span");
        span.textContent = val ?? "-";
        return span;
    }

    function makeDiffCell(diff) {
        const span = document.createElement("span");
        if (diff == null) {
            span.textContent = "-";
        } else {
            span.textContent = diff > 0 ? `+${diff}` : diff;
            span.style.color = diff > 0 ? "green" : diff < 0 ? "red" : "black";
        }
        return span;
    }

    // Initial load
    setTimeout(loadOdds, 500);
});
