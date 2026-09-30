import { initBattleMode, ensureBattleLoaded, getBattleCaption } from './battle.js';
import { initSideBySideMode, adjustImageHeight as adjustSbsHeight, applySideBySideRoute, getSideBySideCaption } from './sideBySide.js';
import { initLeaderboardMode, loadLeaderboardData, selectLeaderboardView, getLeaderboardView, refreshLeaderboardCharts } from './leaderboard.js';
import { initHistoryMode, loadHistoryData, refreshHistoryChart } from './history.js';
import { initCompareMode, applyCompareRoute, refreshCompareCharts } from './compare.js';
import { APP_CONFIG } from './config.js';
import { updateLoginLinks } from './auth.js';
import { showToast } from './toast.js';
import { initTheme } from './theme.js';
import { initLightbox, bindLightbox } from './lightbox.js';
import { initHelp, showHelpSection } from './help.js';

// Nézetek és címük; az útvonal formája: #/<nézet>[/<alnézet>][?paraméterek]
const MODES = {
    battle: 'Arena Battle',
    'side-by-side': 'Side-by-Side',
    leaderboard: 'Leaderboard',
    history: 'Fejlődés',
    compare: 'Összehasonlítás',
    help: 'Súgó',
};
const DEFAULT_MODE = 'battle';
const SITE_TITLE = 'AI Képgenerátor Aréna';
const navLinks = document.querySelectorAll('.navbar-nav .nav-link[data-mode]');
let currentMode = null;

// Régi útvonalak, amelyek új címre költöztek (a megosztott linkek ne romoljanak el)
const LEGACY_ROUTES = { '#/elo-history': '#/history' };

function parseRoute(hash = window.location.hash) {
    if (!hash.startsWith('#/')) return null;
    const legacy = LEGACY_ROUTES[hash.split('?')[0]];
    if (legacy) {
        history.replaceState(null, '', legacy);
        return parseRoute(legacy);
    }
    const [path, query = ''] = hash.slice(2).split('?');
    const [mode, sub = ''] = path.split('/');
    return { mode: MODES[mode] ? mode : DEFAULT_MODE, sub, params: new URLSearchParams(query) };
}

function showMode(modeToShow) {
    Object.keys(MODES).forEach((mode) => {
        const element = document.getElementById(`${mode}-mode`);
        if (!element) return;
        element.style.display = mode === modeToShow ? (mode === 'side-by-side' ? 'flex' : 'block') : 'none';
    });
    navLinks.forEach((link) => {
        const active = link.dataset.mode === modeToShow;
        link.classList.toggle('active', active);
        if (active) link.setAttribute('aria-current', 'page');
        else link.removeAttribute('aria-current');
    });
    document.title = modeToShow === DEFAULT_MODE ? SITE_TITLE : `${MODES[modeToShow]} – ${SITE_TITLE}`;
    if (modeToShow === 'side-by-side') setTimeout(adjustSbsHeight, 0);
}

function closeMobileMenu() {
    const navbarCollapse = document.getElementById('navbarNav');
    if (!navbarCollapse) return;
    const hide = () => {
        if (window.bootstrap?.Collapse) window.bootstrap.Collapse.getOrCreateInstance(navbarCollapse, { toggle: false }).hide();
        else navbarCollapse.classList.remove('show');
        document.querySelector('.navbar-toggler')?.setAttribute('aria-expanded', 'false');
    };
    if (navbarCollapse.classList.contains('collapsing')) {
        navbarCollapse.addEventListener('shown.bs.collapse', hide, { once: true });
    } else if (navbarCollapse.classList.contains('show')) {
        hide();
    }
}

function handleRoute() {
    const route = parseRoute();
    if (!route) return; // Nem nézet-útvonal (pl. #main-content): nincs teendő
    const modeChanged = route.mode !== currentMode;
    currentMode = route.mode;
    showMode(route.mode);
    closeMobileMenu();
    updateLoginLinks();

    switch (route.mode) {
    case 'battle':
        ensureBattleLoaded();
        break;
    case 'side-by-side':
        applySideBySideRoute(route.params);
        break;
    case 'leaderboard':
        if (route.sub && route.sub !== getLeaderboardView()) selectLeaderboardView(route.sub);
        if (modeChanged) loadLeaderboardData();
        break;
    case 'history':
        if (modeChanged) loadHistoryData();
        break;
    case 'compare':
        applyCompareRoute(route.params);
        break;
    case 'help':
        showHelpSection(route.sub); // a görgetést is ez intézi
        return;
    default:
        break;
    }
    if (modeChanged) window.scrollTo({ top: 0 });
}

document.addEventListener('DOMContentLoaded', () => {
    initTheme();
    initLightbox();
    initBattleMode();
    initSideBySideMode();
    initLeaderboardMode();
    initHistoryMode();
    initCompareMode();
    initHelp();

    // Nagyítható képek: a battle-ben a felirat szavazás előtt nem árulja el a modellt
    bindLightbox(document.querySelectorAll('#battle-mode .arena-image'), getBattleCaption);
    bindLightbox(document.querySelectorAll('#side-by-side-mode .arena-image'), getSideBySideCaption);

    // A leaderboard alnézete (fül) is kerüljön az útvonalba, hogy megosztható legyen
    document.addEventListener('leaderboard:viewchange', (event) => {
        if (currentMode !== 'leaderboard') return;
        const view = event.detail.view;
        const hash = view === 'ranking' ? '#/leaderboard' : `#/leaderboard/${view}`;
        if (window.location.hash !== hash) history.replaceState(null, '', hash);
        updateLoginLinks();
    });
    document.addEventListener('route:replaced', updateLoginLinks);

    // Témaváltáskor a vásznon rajzolt diagramok színeit újra kell számolni
    document.addEventListener('themechange', () => {
        refreshLeaderboardCharts();
        refreshHistoryChart();
        refreshCompareCharts();
    });

    // „Ugrás a tartalomra”: fókusz a fő tartalomra az útvonal megváltoztatása nélkül
    document.querySelector('a[href="#main-content"]')?.addEventListener('click', (event) => {
        event.preventDefault();
        const main = document.getElementById('main-content');
        main.tabIndex = -1;
        main.focus();
    });

    if (APP_CONFIG.login_error) {
        showToast('A bejelentkezés nem sikerült vagy megszakadt. Próbáld újra!', 'warning');
        history.replaceState(null, '', `/${window.location.hash}`);
    }

    window.addEventListener('hashchange', handleRoute);
    if (!parseRoute()) history.replaceState(null, '', `#/${DEFAULT_MODE}`);
    handleRoute();
});
