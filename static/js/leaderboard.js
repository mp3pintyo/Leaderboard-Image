import { fetchData } from './api.js';

// DOM elemek
const leaderboardTableBody = document.getElementById('leaderboard-table-body');
const refreshLeaderboardBtn = document.getElementById('refresh-leaderboard-btn');
const modelTypeRadios = document.querySelectorAll('input[name="model-type"]');

// Változók
let currentModelType = 'all'; // Alapértelmezett szűrő: összes modell

// Fő funkciók
export async function loadLeaderboardData() {
    leaderboardTableBody.innerHTML = '<tr><td colspan="7" class="text-center">Leaderboard betöltése...</td></tr>';
    refreshLeaderboardBtn.disabled = true;

    const data = await fetchData(`/api/leaderboard?model_type=${currentModelType}`);
    if (data) {
        leaderboardTableBody.innerHTML = '';
        if (data.length === 0) {
            leaderboardTableBody.innerHTML = '<tr><td colspan="7" class="text-center">Nincs adat a kiválasztott szűrésre</td></tr>';
        } else {
            data.forEach((row, index) => {
                const tr = document.createElement('tr');
                
                // Befagyasztott modellek jelölése
                if (row.frozen) {
                    tr.classList.add('frozen-model');
                }
                
                // Modell típus kijelzése: open source vagy zárt
                const modelType = row.open_source ? 
                    '<span class="badge bg-success">Open Source</span>' : 
                    '<span class="badge bg-warning text-dark">Zárt forrású</span>';
                
                // Befagyasztott állapot jelölése
                const frozenBadge = row.frozen ? 
                    ' <span class="badge bg-secondary" title="Ez a modell jelenleg ki van zárva az Arena Battle-ből">Befagyasztva</span>' : '';
                
                tr.innerHTML = `
                    <td>${index + 1}</td>
                    <td>${row.name}${frozenBadge}</td>
                    <td><strong>${row.elo}</strong></td>
                    <td>${row.wins}</td>
                    <td>${row.matches}</td>
                    <td>${row.win_rate}%</td>
                    <td>${modelType}</td>
                `;
                leaderboardTableBody.appendChild(tr);
            });
        }
    } else {
        leaderboardTableBody.innerHTML = '<tr><td colspan="7" class="text-center">Hiba a leaderboard betöltése közben.</td></tr>';
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
            // Frissítsük a jelenlegi szűrési típust
            currentModelType = e.target.value;
            // Töltsük be az adatokat az új szűrővel
            loadLeaderboardData();
        });
    });
}
