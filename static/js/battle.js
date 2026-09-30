import { requestJson } from './api.js';
import { getRevealDelayMs } from './config.js';
import { isLoggedIn, showLoginPrompt } from './auth.js';
import { preloadImages } from './imageLoading.js';
import { showToast } from './toast.js';

// DOM elemek
const battleModeDiv = document.getElementById('battle-mode');
const battlePrompt = document.getElementById('battle-prompt');
const battlePromptPopup = document.getElementById('battle-prompt-popup');
const slots = {
    a: {
        root: document.getElementById('battle-slot-a'),
        name: document.getElementById('battle-model1-name'),
        delta: document.getElementById('battle-delta-a'),
        image: document.getElementById('battle-image1'),
    },
    b: {
        root: document.getElementById('battle-slot-b'),
        name: document.getElementById('battle-model2-name'),
        delta: document.getElementById('battle-delta-b'),
        image: document.getElementById('battle-image2'),
    },
};
const voteButtons = {
    a: document.getElementById('vote-btn1'),
    b: document.getElementById('vote-btn2'),
    tie: document.getElementById('tie-btn'),
    both_bad: document.getElementById('both-bad-btn'),
};
const skipBtn = document.getElementById('skip-btn');
const voteCounter = document.getElementById('battle-vote-counter');

// Állapot
let current = null;        // { battle, receivedAt }
let prefetched = null;     // Promise<{ battle, receivedAt }> – a következő pár, már előtöltött képekkel
let busy = false;
let enableTimer = null;
let dailyLimitReached = false;

const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

async function fetchBattle() {
    const battle = await requestJson('/api/battle_data');
    const receivedAt = performance.now();
    await preloadImages([battle.image_a, battle.image_b]);
    return { battle, receivedAt };
}

/** A következő pár letöltése és képeinek dekódolása, amíg az eredményt mutatjuk. */
function startPrefetch() {
    if (!prefetched) {
        prefetched = fetchBattle();
        prefetched.catch(() => {}); // A hibát a felhasználáskor kezeljük
    }
}

function takeNextBattle() {
    const pending = prefetched || fetchBattle();
    prefetched = null;
    return pending;
}

function setVotingEnabled(enabled) {
    Object.values(voteButtons).forEach((button) => { button.disabled = !enabled; });
}

function disableAll() {
    clearTimeout(enableTimer);
    setVotingEnabled(false);
    skipBtn.disabled = true;
}

function resetReveal() {
    Object.values(slots).forEach((slot, index) => {
        slot.root.classList.remove('is-winner', 'is-loser', 'is-tie', 'is-bad', 'is-revealed');
        slot.name.textContent = index === 0 ? 'Modell A' : 'Modell B';
        slot.delta.hidden = true;
        slot.delta.textContent = '';
        slot.delta.removeAttribute('title');
    });
}

function formatScore(value, digits = 0) {
    return Number(value).toLocaleString('hu-HU', { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

function formatDelta(delta) {
    if (!delta) return '±0';
    return `${delta > 0 ? '+' : '−'}${formatScore(Math.abs(delta), 1)}`;
}

/** „1913 → 1915”; ha kerekítve azonos lenne, egy tizedessel mutatjuk, hogy látszódjon az elmozdulás. */
function formatScoreChange(before, after) {
    const digits = Math.round(before) === Math.round(after) && before !== after ? 1 : 0;
    return `${formatScore(before, digits)} → ${formatScore(after, digits)}`;
}

function revealModels(result, choice) {
    ['a', 'b'].forEach((side) => {
        const slot = slots[side];
        const model = result[`model_${side}`];
        slot.root.classList.add('is-revealed');
        slot.name.textContent = model.display;
        if (choice === side) slot.root.classList.add('is-winner');
        else if (choice === 'a' || choice === 'b') slot.root.classList.add('is-loser');
        else if (choice === 'tie') slot.root.classList.add('is-tie');
        else if (choice === 'both_bad') slot.root.classList.add('is-bad');

        // A Leaderboard (Bradley-Terry) pontszám változása – ugyanaz a szám, ami a rangsorban látszik
        if (typeof model.score_delta === 'number') {
            const tone = model.score_delta > 0.05 ? 'text-bg-success' : model.score_delta < -0.05 ? 'text-bg-danger' : 'text-bg-secondary';
            slot.delta.textContent = formatScoreChange(model.score_before, model.score_after);
            slot.delta.className = `elo-delta ${tone}`;
            slot.delta.title = `Leaderboard-pontszám: ${formatScoreChange(model.score_before, model.score_after)} (${formatDelta(model.score_delta)}). Részletek: Súgó → Mi történik a szavazatod után?`;
            slot.delta.setAttribute('aria-label', `Pontszám ${formatScore(model.score_before)}-ról ${formatScore(model.score_after)}-ra változott`);
            slot.delta.hidden = false;
        }
    });
}

function updateVoteCounter(result) {
    if (!voteCounter || typeof result.votes_today !== 'number') return;
    voteCounter.textContent = `Mai szavazataid: ${result.votes_today} / ${result.daily_limit}`;
    dailyLimitReached = result.votes_today >= result.daily_limit;
}

function scheduleVotingEnable() {
    clearTimeout(enableTimer);
    if (!current || !isLoggedIn() || dailyLimitReached) return;
    const { battle, receivedAt } = current;
    const remaining = Math.max(0, battle.vote_delay_ms - (performance.now() - receivedAt)) + 50;
    enableTimer = setTimeout(() => {
        if (!busy) setVotingEnabled(true);
    }, remaining);
}

function showBattle(next) {
    current = next;
    const { battle } = next;
    const fullPromptText = `Prompt: "${battle.prompt_text}" (ID: ${battle.prompt_id})`;
    battlePrompt.textContent = fullPromptText;
    battlePromptPopup.textContent = fullPromptText;
    setPromptOpen(false);
    resetReveal();
    // A képek már le vannak töltve és dekódolva, így nincs üres/villogó képterület
    slots.a.image.src = battle.image_a;
    slots.b.image.src = battle.image_b;
    skipBtn.disabled = false;
    if (isLoggedIn()) {
        scheduleVotingEnable();
    } else {
        showLoginPrompt();
    }
}

/** Útvonalváltáskor: csak akkor tölt új párt, ha még nincs megjelenített (így nem „ég el” a látott pár). */
export function ensureBattleLoaded() {
    if (!current && !busy) loadBattleData();
}

/** A nagyított kép felirata: szavazás előtt csak az oldal, utána a modell neve. */
export function getBattleCaption(img) {
    const slot = img === slots.a.image ? slots.a : slots.b;
    const side = slot === slots.a ? 'A' : 'B';
    const name = slot.name.textContent;
    return name === `Modell ${side}` ? `${side} oldali kép` : `${side}: ${name}`;
}

export async function loadBattleData() {
    if (busy) return;
    busy = true;
    disableAll();
    if (!current) battlePrompt.textContent = 'Új prompt betöltése...';
    try {
        showBattle(await takeNextBattle());
    } catch (error) {
        console.error('Battle load failed:', error);
        current = null;
        showToast(error.message || 'Hiba a battle betöltése közben.', 'danger');
        battlePrompt.textContent = 'Hiba a betöltés közben. Kattints a Kihagyás gombra az újrapróbáláshoz.';
        skipBtn.disabled = false;
    } finally {
        busy = false;
    }
}

async function handleChoice(choice) {
    if (!current || busy) return;
    if (!isLoggedIn()) {
        showLoginPrompt();
        return;
    }
    busy = true;
    disableAll();
    startPrefetch();
    const battleId = current.battle.battle_id;
    try {
        const result = await requestJson('/api/vote', { method: 'POST', json: { battle_id: battleId, choice } });
        revealModels(result, choice);
        updateVoteCounter(result);
        await wait(getRevealDelayMs());
    } catch (error) {
        if (error.code === 'too_fast') {
            // A pár még érvényes: csak várni kell egy kicsit
            showToast(error.message, 'warning');
            busy = false;
            skipBtn.disabled = false;
            scheduleVotingEnable();
            return;
        }
        if (error.code === 'daily_limit') dailyLimitReached = true;
        if (error.status === 401) showLoginPrompt();
        showToast(error.message, error.status >= 500 ? 'danger' : 'warning');
    }
    busy = false;
    loadBattleData();
}

async function handleSkip() {
    if (busy) return;
    if (!current) {
        loadBattleData();
        return;
    }
    busy = true;
    disableAll();
    startPrefetch();
    try {
        const result = await requestJson('/api/battle/skip', { method: 'POST', json: { battle_id: current.battle.battle_id } });
        revealModels(result, null);
        await wait(Math.min(getRevealDelayMs(), 1200));
    } catch (error) {
        // Lejárt vagy már lezárt pár: egyszerűen jöhet a következő
        console.warn('Skip failed:', error);
    }
    busy = false;
    loadBattleData();
}

function setPromptOpen(open) {
    battlePromptPopup.style.display = open ? 'block' : 'none';
    battlePrompt.classList.toggle('prompt-open', open);
    battlePrompt.setAttribute('aria-expanded', String(open));
}

function isBattleVisible() {
    return battleModeDiv.offsetParent !== null;
}

export function initBattleMode() {
    voteButtons.a.addEventListener('click', () => handleChoice('a'));
    voteButtons.b.addEventListener('click', () => handleChoice('b'));
    voteButtons.tie.addEventListener('click', () => handleChoice('tie'));
    voteButtons.both_bad.addEventListener('click', () => handleChoice('both_bad'));
    skipBtn.addEventListener('click', handleSkip);

    // Prompt kinyitása/becsukása kattintásra vagy Enter/Space billentyűre
    const togglePrompt = () => setPromptOpen(battlePromptPopup.style.display === 'none');
    battlePrompt.addEventListener('click', togglePrompt);
    battlePrompt.addEventListener('keydown', (event) => {
        if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault();
            togglePrompt();
        }
    });

    const keyMap = {
        '1': 'a', 'ArrowLeft': 'a',
        '2': 'b', 'ArrowRight': 'b',
        '0': 'tie', 't': 'tie', 'T': 'tie',
        'x': 'both_bad', 'X': 'both_bad',
    };

    document.addEventListener('keydown', (event) => {
        if (event.ctrlKey || event.metaKey || event.altKey || event.defaultPrevented) return;
        const target = event.target;
        if (['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName) || target.isContentEditable) return;
        if (!isBattleVisible() || document.body.classList.contains('modal-open')) return;

        if (event.key === 's' || event.key === 'S') {
            if (!skipBtn.disabled) skipBtn.click();
            return;
        }
        const choice = keyMap[event.key];
        if (choice && !voteButtons[choice].disabled) {
            event.preventDefault();
            voteButtons[choice].click();
        }
    });
}
