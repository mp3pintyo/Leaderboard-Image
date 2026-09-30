// Súgó oldal: fejezetre ugrás útvonalból (#/help/<fejezet>), aktív fejezet kiemelése, élő statisztika
import { requestJson } from './api.js';

const helpMode = document.getElementById('help-mode');
const tocLinks = document.querySelectorAll('[data-help-link]');
const statsContainer = document.getElementById('help-stats');
const statsNote = document.getElementById('help-stats-note');

let statsLoadedAt = 0;
let observer = null;
let ignoreObserverUntil = 0; // programozott ugrás után a görgetésfigyelő ne írja felül a kijelölést

function formatNumber(value, digits = 0) {
    return Number(value).toLocaleString('hu-HU', { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

function setActiveLink(section) {
    tocLinks.forEach((link) => {
        const active = link.dataset.helpLink === section;
        link.classList.toggle('active', active);
        if (active) link.setAttribute('aria-current', 'true');
        else link.removeAttribute('aria-current');
    });
}

function statItem(label, value, hint = '') {
    const item = document.createElement('div');
    item.className = 'leaderboard-stat';
    const labelEl = document.createElement('span');
    labelEl.className = 'leaderboard-stat-label';
    labelEl.textContent = label;
    const valueEl = document.createElement('strong');
    valueEl.textContent = value;
    item.append(labelEl, valueEl);
    if (hint) {
        const hintEl = document.createElement('small');
        hintEl.className = 'd-block text-body-secondary';
        hintEl.textContent = hint;
        item.appendChild(hintEl);
    }
    return item;
}

async function loadStats() {
    // Legfeljebb percenként frissítjük
    if (Date.now() - statsLoadedAt < 60_000) return;
    statsLoadedAt = Date.now();
    try {
        const stats = await requestJson('/api/leaderboard/stats');
        const bias = stats.position_bias;
        const share = (value) => (stats.total_votes ? ` (${formatNumber((value / stats.total_votes) * 100, 1)}%)` : '');
        let biasValue = 'még nincs elég adat';
        let biasHint = 'Az oldal naplózása 2026. szeptember 30-án indult.';
        if (bias.left_win_rate !== null) {
            biasValue = `${formatNumber(bias.left_win_rate, 1)}%`;
            const neutral = bias.ci_lower <= 50 && bias.ci_upper >= 50;
            biasHint = `95% CI: ${formatNumber(bias.ci_lower, 1)}–${formatNumber(bias.ci_upper, 1)}%, ${formatNumber(bias.votes)} szavazatból – `
                + (neutral ? 'nincs kimutatható oldaltorzítás.' : 'kimutatható oldaltorzítás.');
        }
        statsContainer.replaceChildren(
            statItem('Összes szavazat', formatNumber(stats.total_votes)),
            statItem('Döntő szavazat (A vagy B)', formatNumber(stats.decisive_votes) + share(stats.decisive_votes)),
            statItem('Döntetlen', formatNumber(stats.ties) + share(stats.ties)),
            statItem('Mindkettő rossz', formatNumber(stats.both_bad) + share(stats.both_bad)),
            statItem('Bejelentkezett szavazók', formatNumber(stats.voters), 'A bejelentkezés bevezetése előtti szavazatok nélkül.'),
            statItem('Bal oldali kép nyerési aránya', biasValue, biasHint),
        );
        const computed = new Date(stats.method.computed_at).toLocaleString('hu-HU', { dateStyle: 'medium', timeStyle: 'short' });
        statsNote.textContent = `Módszer: ${stats.method.name}, ${stats.method.bootstrap_rounds} bootstrap kör; a konfidenciaintervallumok utolsó számítása: ${computed}.`;
    } catch (error) {
        statsLoadedAt = 0;
        statsContainer.replaceChildren(Object.assign(document.createElement('p'), {
            className: 'text-body-secondary mb-0', textContent: 'A statisztika most nem tölthető be.',
        }));
    }
}

/** Útvonalváltáskor: a megadott fejezetre görget (vagy az oldal tetejére). */
export function showHelpSection(section) {
    loadStats();
    const target = section ? document.getElementById(`help-${section}`) : null;
    ignoreObserverUntil = performance.now() + 1000;
    requestAnimationFrame(() => {
        if (target) {
            const navHeight = document.querySelector('.navbar')?.offsetHeight || 56;
            window.scrollTo({ top: target.getBoundingClientRect().top + window.scrollY - navHeight - 12 });
            target.setAttribute('tabindex', '-1');
            target.focus({ preventScroll: true });
            setActiveLink(section);
        } else {
            window.scrollTo({ top: 0 });
            setActiveLink('gyorsan');
        }
    });
}

export function initHelp() {
    if (!helpMode) return;
    // Görgetés közben a tartalomjegyzék mutatja, melyik fejezetnél tartasz
    observer = new IntersectionObserver((entries) => {
        if (helpMode.style.display === 'none' || performance.now() < ignoreObserverUntil) return;
        const visible = entries.filter((entry) => entry.isIntersecting)
            .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top);
        if (visible.length) setActiveLink(visible[0].target.id.replace('help-', ''));
    }, { rootMargin: '-80px 0px -65% 0px' });
    helpMode.querySelectorAll('.help-section').forEach((section) => observer.observe(section));

    // Ugyanarra a fejezetre mutató link újbóli kattintásakor nincs hashchange, ezért kézzel görgetünk
    helpMode.addEventListener('click', (event) => {
        const link = event.target.closest('a[href^="#/help"]');
        if (link && link.getAttribute('href') === window.location.hash) {
            event.preventDefault();
            showHelpSection(link.getAttribute('href').split('/')[2] || '');
        }
    });
}
