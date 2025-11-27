import { initBattleMode, loadBattleData } from './battle.js';
import { initSideBySideMode } from './sideBySide.js';
import { initLeaderboardMode, loadLeaderboardData } from './leaderboard.js';
import { initEloHistoryMode, loadEloHistoryData } from './eloHistory.js';

// DOM elemek
const modes = ['battle', 'side-by-side', 'leaderboard', 'elo-history'];
const navLinks = document.querySelectorAll('.navbar-nav .nav-link');

// Segédfüggvények
function showMode(modeToShow) {
    modes.forEach(mode => {
        const element = document.getElementById(`${mode}-mode`);
        if (element) {
            element.style.display = mode === modeToShow ? 'block' : 'none';
        }
    });
    
    navLinks.forEach(link => {
        if (link.dataset.mode === modeToShow) {
            link.classList.add('active');
        } else {
            link.classList.remove('active');
        }
    });
}

// Inicializáció
document.addEventListener('DOMContentLoaded', function() {
    // Modulok inicializálása
    initBattleMode();
    initSideBySideMode();
    initLeaderboardMode();
    initEloHistoryMode();

    // Navigáció kezelése
    navLinks.forEach(link => {
        link.addEventListener('click', (e) => {
            e.preventDefault();
            const mode = link.dataset.mode;
            showMode(mode);

            // Az aktuális mód adatainak betöltése
            if (mode === 'battle') {
                loadBattleData();
            } else if (mode === 'leaderboard') {
                loadLeaderboardData();
            } else if (mode === 'elo-history') {
                loadEloHistoryData();
            }
        });
    });

    // Kezdeti mód beállítása
    showMode('battle');
    loadBattleData();
});
