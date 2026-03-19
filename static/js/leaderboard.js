import { fetchData } from './api.js';

// DOM elemek
const leaderboardTableBody = document.getElementById('leaderboard-table-body');
const refreshLeaderboardBtn = document.getElementById('refresh-leaderboard-btn');
const modelTypeRadios = document.querySelectorAll('input[name="model-type"]');
const myVotesSubfilter = document.getElementById('my-votes-subfilter');
const myTypeRadios = document.querySelectorAll('input[name="my-type"]');

// Változók
let currentModelType = 'all'; // Alapértelmezett szűrő: összes modell
let currentMySubType = 'all'; // Saját toplista al-szűrő

function renderRows(rows) {
    leaderboardTableBody.innerHTML = '';
    if (rows.length === 0) {
        leaderboardTableBody.innerHTML = '<tr><td colspan="7" class="text-center">Nincs adat a kiválasztott szűrésre</td></tr>';
        return;
    }
    rows.forEach((row, index) => {
        const tr = document.createElement('tr');
        if (row.frozen) tr.classList.add('frozen-model');
        const modelType = row.open_source ?
            '<span class="badge bg-success">Open Source</span>' :
            '<span class="badge bg-warning text-dark">Zárt forrású</span>';
        const frozenBadge = row.frozen ?
            ' <span class="badge bg-secondary" title="Ez a modell jelenleg ki van zárva az Arena Battle-ből">Befagyasztva</span>' : '';
        const modelDisplayName = row.display || (row.provider ? `${row.provider}: ${row.name}` : row.name);
        tr.innerHTML = `
            <td>${index + 1}</td>
            <td>${modelDisplayName}${frozenBadge}</td>
            <td><strong>${row.elo}</strong></td>
            <td>${row.wins}</td>
            <td>${row.matches}</td>
            <td>${row.win_rate}%</td>
            <td>${modelType}</td>
        `;
        leaderboardTableBody.appendChild(tr);
    });
}

// Fő funkciók
export async function loadLeaderboardData() {
    leaderboardTableBody.innerHTML = '<tr><td colspan="7" class="text-center">Leaderboard betöltése...</td></tr>';
    refreshLeaderboardBtn.disabled = true;

    // Saját toplista info-sáv kezelése
    let infoBar = document.getElementById('personal-leaderboard-info');

    if (currentModelType === 'my-votes') {
        const data = await fetchData(`/api/leaderboard/mine?model_type=${currentMySubType}`);
        if (data) {
            // Info sáv megjelenítése
            if (!infoBar) {
                infoBar = document.createElement('div');
                infoBar.id = 'personal-leaderboard-info';
                infoBar.className = 'alert alert-info text-center mb-3';
                leaderboardTableBody.closest('table').before(infoBar);
            }
            if (data.vote_count === 0) {
                infoBar.textContent = 'Még nem adtál le szavazatot. Szavazz az Arena Battle módban, hogy megjelenjen a saját toplistád!';
            } else {
                infoBar.textContent = `A toplista a te ${data.vote_count} szavazatod alapján lett kiszámítva.`;
            }
            renderRows(data.leaderboard);
        } else {
            leaderboardTableBody.innerHTML = '<tr><td colspan="7" class="text-center">Hiba a leaderboard betöltése közben.</td></tr>';
        }
    } else {
        // Info sáv elrejtése normál módban
        if (infoBar) infoBar.remove();

        const data = await fetchData(`/api/leaderboard?model_type=${currentModelType}`);
        if (data) {
            renderRows(data);
        } else {
            leaderboardTableBody.innerHTML = '<tr><td colspan="7" class="text-center">Hiba a leaderboard betöltése közben.</td></tr>';
        }
    }

    refreshLeaderboardBtn.disabled = false;
}

// Event listeners
export function initLeaderboardMode() {
    // Frissítés gomb eseménykezelő
    refreshLeaderboardBtn.addEventListener('click', loadLeaderboardData);
    
    // Modell típus szűrők eseménykezelői
    modelTypeRadios.forEach(radio => {
        radio.addEventListener('change', (e) => {
            currentModelType = e.target.value;
            // Al-szűrő megjelenítése/elrejtése
            myVotesSubfilter.style.display = currentModelType === 'my-votes' ? 'flex' : 'none';
            loadLeaderboardData();
        });
    });

    // Saját toplista al-szűrők
    myTypeRadios.forEach(radio => {
        radio.addEventListener('change', (e) => {
            currentMySubType = e.target.value;
            loadLeaderboardData();
        });
    });
}
