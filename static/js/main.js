import { initBattleMode, loadBattleData } from './battle.js';
import { initSideBySideMode, adjustImageHeight as adjustSbsHeight } from './sideBySide.js';
import { initLeaderboardMode, loadLeaderboardData } from './leaderboard.js';
import { initEloHistoryMode, loadEloHistoryData } from './eloHistory.js';
import { initCompareMode, loadCompareData } from './compare.js';
import { APP_CONFIG } from './config.js';
import { updateLoginLinks } from './auth.js';
import { showToast } from './toast.js';

// DOM elemek
const modes = ['battle', 'side-by-side', 'leaderboard', 'elo-history', 'compare'];
const navLinks = document.querySelectorAll('.navbar-nav .nav-link');

// Segédfüggvények
function showMode(modeToShow) {
    modes.forEach(mode => {
        const element = document.getElementById(`${mode}-mode`);
        if (element) {
            if (mode === modeToShow) {
                element.style.display = mode === 'side-by-side' ? 'flex' : 'block';
            } else {
                element.style.display = 'none';
            }
        }
    });
    
    navLinks.forEach(link => {
        if (link.dataset.mode === modeToShow) {
            link.classList.add('active');
        } else {
            link.classList.remove('active');
        }
    });

    if (modeToShow === 'side-by-side') {
        setTimeout(adjustSbsHeight, 0);
    }
}

// Inicializáció
document.addEventListener('DOMContentLoaded', function() {
    // Modulok inicializálása
    initBattleMode();
    initSideBySideMode();
    initLeaderboardMode();
    initEloHistoryMode();
    initCompareMode();

    // Navigáció kezelése
    navLinks.forEach(link => {
        if (!link.hasAttribute('data-mode')) return; // Ne kezelje a külső linkeket, mint pl. a GitHub
        link.addEventListener('click', (e) => {
            e.preventDefault();
            const mode = link.dataset.mode;
            showMode(mode);

            const navbarCollapse = document.getElementById('navbarNav');
            if (navbarCollapse?.classList.contains('collapsing') && window.bootstrap?.Collapse) {
                navbarCollapse.addEventListener('shown.bs.collapse', () => {
                    window.bootstrap.Collapse.getOrCreateInstance(navbarCollapse).hide();
                }, { once: true });
            } else if (navbarCollapse?.classList.contains('show')) {
                if (window.bootstrap?.Collapse) {
                    window.bootstrap.Collapse.getOrCreateInstance(navbarCollapse).hide();
                } else {
                    navbarCollapse.classList.remove('show');
                    document.querySelector('.navbar-toggler')?.setAttribute('aria-expanded', 'false');
                }
            }

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

    updateLoginLinks();
    if (APP_CONFIG.login_error) {
        showToast('A bejelentkezés nem sikerült vagy megszakadt. Próbáld újra!', 'warning');
    }

    // Kezdeti mód beállítása
    showMode('battle');
    loadBattleData();
});
