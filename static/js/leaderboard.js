import { createVideoLink } from './videoLink.js';
import { requestJson } from './api.js';
import { getModels } from './config.js';
import { showToast } from './toast.js';
import { showLoginPrompt } from './auth.js';
import { chartTheme } from './theme.js';

const leaderboardTableBody = document.getElementById('leaderboard-table-body');
const refreshLeaderboardBtn = document.getElementById('refresh-leaderboard-btn');
const modelTypeRadios = document.querySelectorAll('input[name="model-type"]');
const myVotesSubfilter = document.getElementById('my-votes-subfilter');
const myTypeRadios = document.querySelectorAll('input[name="my-type"]');
const viewCards = document.querySelectorAll('[data-leaderboard-view]');
const panels = {
    ranking: document.getElementById('leaderboard-ranking-panel'),
    'quality-price': document.getElementById('leaderboard-quality-price-panel'),
    matrix: document.getElementById('leaderboard-matrix-panel'),
};
const qualityPriceLimitRadios = document.querySelectorAll('input[name="quality-price-limit"]');
const qualityPriceEmpty = document.getElementById('quality-price-empty');
const columnToggles = document.querySelectorAll('.leaderboard-column-toggle');
const columnHeaders = document.querySelectorAll('[data-column-header]');
const sortHeaders = document.querySelectorAll('th[data-sort]');
const searchInput = document.getElementById('leaderboard-search');
const providerSelect = document.getElementById('leaderboard-provider');
const hidePreliminaryToggle = document.getElementById('leaderboard-hide-preliminary');
const personalInfo = document.getElementById('personal-leaderboard-info');
const countLabel = document.getElementById('leaderboard-count');
const summaryLabel = document.getElementById('leaderboard-summary');
const methodDetails = document.getElementById('leaderboard-method');
const statsGrid = document.getElementById('leaderboard-stats');
const matrixContainer = document.getElementById('matrix-container');
const matrixMetricRadios = document.querySelectorAll('input[name="matrix-metric"]');
const matrixTopSelect = document.getElementById('matrix-top');

const leaderboardColumnsStorageKey = 'leaderboard-visible-columns';
const optionalColumns = ['record', 'elo', 'release_date', 'max_resolution', 'pricing', 'video_url'];
const BASE_COLUMN_COUNT = 7;

// Rendezés: alapértelmezett irány kulcsonként
const SORT_DEFAULT_DIRECTION = {
    rank: 'asc', display: 'asc', ci_width: 'asc', price_per_1000: 'asc',
    score: 'desc', matches: 'desc', win_rate: 'desc', open_source: 'desc', wins: 'desc', elo: 'desc', release_date: 'desc',
};

const state = {
    modelType: 'all',
    mySubType: 'all',
    search: '',
    provider: '',
    hidePreliminary: false,
    sort: { key: 'score', direction: 'desc' },
    visibleColumns: new Set(),
    rows: [],
    personal: null,
    view: 'ranking',
    qualityPriceLimit: 10,
    matrixMetric: 'win_rate',
    matrixTop: 12,
};

let baseLeaderboard = null;
let qualityPriceChart = null;
let loadController = null;
let matrixData = null;
let statsLoaded = false;

function storageGet(key) {
    try { return localStorage.getItem(key); } catch { return null; }
}

function storageSet(key, value) {
    try { localStorage.setItem(key, value); } catch { /* privát mód */ }
}

function getColumnCount() {
    return BASE_COLUMN_COUNT + state.visibleColumns.size;
}

function updateColumnVisibility() {
    columnHeaders.forEach((header) => {
        header.hidden = !state.visibleColumns.has(header.dataset.columnHeader);
    });
    columnToggles.forEach((toggle) => {
        toggle.checked = state.visibleColumns.has(toggle.dataset.column);
    });
}

function loadVisibleColumns() {
    try {
        const stored = JSON.parse(storageGet(leaderboardColumnsStorageKey) || '[]');
        state.visibleColumns = new Set(Array.isArray(stored) ? stored.filter((column) => optionalColumns.includes(column)) : []);
    } catch {
        state.visibleColumns = new Set();
    }
    updateColumnVisibility();
}

function saveVisibleColumns() {
    storageSet(leaderboardColumnsStorageKey, JSON.stringify([...state.visibleColumns]));
}

function populateProviders() {
    const providers = [...new Set(getModels().map((m) => m.provider).filter(Boolean))]
        .sort((a, b) => a.localeCompare(b, 'hu'));
    providers.forEach((provider) => {
        const option = document.createElement('option');
        option.value = provider;
        option.textContent = provider;
        providerSelect.appendChild(option);
    });
}

function messageRow(text) {
    const tr = document.createElement('tr');
    const td = document.createElement('td');
    td.colSpan = getColumnCount();
    td.className = 'text-center text-body-secondary py-4';
    td.textContent = text;
    tr.appendChild(td);
    return tr;
}

function showMessage(text) {
    leaderboardTableBody.replaceChildren(messageRow(text));
    countLabel.textContent = '';
}

function sortValue(row, key) {
    switch (key) {
    case 'ci_width':
        return row.ci_lower === null ? null : row.ci_upper - row.ci_lower;
    case 'display':
        return row.display.toLocaleLowerCase('hu');
    case 'open_source':
        return row.open_source ? 1 : 0;
    case 'release_date':
        return row.release_date || null;
    case 'price_per_1000':
        return Number.isFinite(row.price_per_1000) ? row.price_per_1000 : null;
    default:
        return row[key] ?? null;
    }
}

function getVisibleRows() {
    const query = state.search.trim().toLocaleLowerCase('hu');
    const { key, direction } = state.sort;
    const factor = direction === 'asc' ? 1 : -1;
    return state.rows
        .filter((row) => !query || row.display.toLocaleLowerCase('hu').includes(query))
        .filter((row) => !state.provider || row.provider === state.provider)
        .filter((row) => !state.hidePreliminary || !row.preliminary)
        .slice()
        .sort((a, b) => {
            const av = sortValue(a, key);
            const bv = sortValue(b, key);
            if (av === bv) return b.score - a.score;
            if (av === null) return 1; // Hiányzó érték mindig a végére
            if (bv === null) return -1;
            return (av < bv ? -1 : 1) * factor;
        });
}

function formatNumber(value, digits = 0) {
    return Number(value).toLocaleString('hu-HU', { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

function createBadge(text, className, title = '') {
    const badge = document.createElement('span');
    badge.className = `badge ${className}`;
    badge.textContent = text;
    if (title) badge.title = title;
    return badge;
}

function createCell(content, className = '') {
    const td = document.createElement('td');
    if (className) td.className = className;
    if (content instanceof Node) td.appendChild(content);
    else td.textContent = content;
    return td;
}

function createCiCell(row, range) {
    const td = document.createElement('td');
    td.className = 'ci-cell';
    if (row.ci_lower === null || row.ci_upper === null) {
        td.textContent = '–';
        return td;
    }
    const plus = Math.round(row.ci_upper - row.score);
    const minus = Math.round(row.score - row.ci_lower);
    const text = document.createElement('span');
    text.className = 'ci-text';
    text.textContent = `+${plus} / −${minus}`;
    td.title = `95% CI: ${formatNumber(row.ci_lower)} – ${formatNumber(row.ci_upper)}`;

    const bar = document.createElement('span');
    bar.className = 'ci-bar';
    bar.setAttribute('aria-hidden', 'true');
    const span = Math.max(range.max - range.min, 1);
    const band = document.createElement('span');
    band.className = 'ci-band';
    band.style.left = `${((row.ci_lower - range.min) / span) * 100}%`;
    band.style.width = `${Math.max(((row.ci_upper - row.ci_lower) / span) * 100, 1.5)}%`;
    const point = document.createElement('span');
    point.className = 'ci-point';
    point.style.left = `${((row.score - range.min) / span) * 100}%`;
    bar.append(band, point);
    td.append(text, bar);
    return td;
}

function renderRows() {
    const rows = getVisibleRows();
    if (state.modelType === 'my-votes' && state.personal && !state.personal.unlocked) {
        showMessage('A saját toplista még zárolva van.');
        return;
    }
    if (rows.length === 0) {
        showMessage(state.rows.length ? 'Nincs a szűrésnek megfelelő modell.' : 'Nincs adat a kiválasztott szűrésre.');
        return;
    }

    const withCi = rows.filter((row) => row.ci_lower !== null);
    const range = withCi.length
        ? { min: Math.min(...withCi.map((r) => r.ci_lower)), max: Math.max(...withCi.map((r) => r.ci_upper)) }
        : { min: 0, max: 1 };

    const fragment = document.createDocumentFragment();
    rows.forEach((row) => {
        const tr = document.createElement('tr');
        if (row.frozen) tr.classList.add('frozen-model');
        if (row.preliminary) tr.classList.add('preliminary-model');

        const rankText = row.rank === null ? '–'
            : row.rank_worst && row.rank_worst !== row.rank ? `${row.rank}–${row.rank_worst}` : String(row.rank);
        const rankTd = createCell(rankText, 'rank-cell');
        if (row.rank_worst && row.rank_worst !== row.rank) {
            rankTd.title = `A bizonytalanság miatt a valós helyezés ${row.rank}. és ${row.rank_worst}. között lehet`;
        }
        tr.appendChild(rankTd);

        const modelTd = document.createElement('td');
        modelTd.className = 'model-cell';
        const name = document.createElement('span');
        name.className = 'model-name';
        name.textContent = row.display;
        modelTd.appendChild(name);
        if (row.preliminary) {
            modelTd.append(' ', createBadge('Előzetes', 'text-bg-warning', `Kevesebb mint ${window.APP_CONFIG?.preliminary_threshold ?? 30} meccs – a pontszám még bizonytalan`));
        }
        if (row.frozen) {
            modelTd.append(' ', createBadge('Befagyasztva', 'text-bg-secondary', 'Ez a modell jelenleg ki van zárva az Arena Battle-ből'));
        }
        tr.appendChild(modelTd);

        const scoreStrong = document.createElement('strong');
        scoreStrong.textContent = formatNumber(row.score);
        tr.appendChild(createCell(scoreStrong, 'score-cell'));
        tr.appendChild(createCiCell(row, range));
        tr.appendChild(createCell(formatNumber(row.matches)));
        tr.appendChild(createCell(`${formatNumber(row.win_rate, 1)}%`));
        tr.appendChild(createCell(row.open_source
            ? createBadge('Open Source', 'text-bg-success')
            : createBadge('Zárt forrású', 'text-bg-warning')));

        optionalColumns.forEach((column) => {
            if (!state.visibleColumns.has(column)) return;
            if (column === 'video_url') {
                tr.appendChild(createCell(createVideoLink(row)));
            } else if (column === 'record') {
                tr.appendChild(createCell(`${row.wins} / ${row.ties ?? 0} / ${row.losses ?? 0}`, 'text-nowrap'));
            } else if (column === 'elo') {
                tr.appendChild(createCell(formatNumber(row.elo, 1)));
            } else {
                tr.appendChild(createCell(row[column] || 'N/A'));
            }
        });

        fragment.appendChild(tr);
    });
    leaderboardTableBody.replaceChildren(fragment);
    countLabel.textContent = rows.length === state.rows.length
        ? `${rows.length} modell`
        : `${rows.length} modell megjelenítve (összesen ${state.rows.length})`;
}

function updateSortHeaders() {
    sortHeaders.forEach((th) => {
        const active = th.dataset.sort === state.sort.key;
        th.setAttribute('aria-sort', active ? (state.sort.direction === 'asc' ? 'ascending' : 'descending') : 'none');
    });
}

function renderPersonalInfo() {
    if (state.modelType !== 'my-votes' || !state.personal) {
        personalInfo.hidden = true;
        return;
    }
    const { vote_count: votes, min_votes: minVotes, unlocked } = state.personal;
    personalInfo.hidden = false;
    personalInfo.replaceChildren();
    if (unlocked) {
        personalInfo.textContent = `A toplista a te ${votes} szavazatod alapján készült (Bradley-Terry, csak a te döntéseid).`;
        return;
    }
    const text = document.createElement('div');
    text.textContent = `A saját toplistád ${minVotes} szavazat után nyílik meg – még ${minVotes - votes} szavazat kell. Szavazz az Arena Battle módban!`;
    const progress = document.createElement('div');
    progress.className = 'progress mt-2';
    progress.setAttribute('role', 'progressbar');
    progress.setAttribute('aria-valuemin', '0');
    progress.setAttribute('aria-valuemax', String(minVotes));
    progress.setAttribute('aria-valuenow', String(votes));
    progress.setAttribute('aria-label', 'Szavazatok a saját toplistáig');
    const bar = document.createElement('div');
    bar.className = 'progress-bar';
    bar.style.width = `${Math.min(100, (votes / minVotes) * 100)}%`;
    bar.textContent = `${votes} / ${minVotes}`;
    progress.appendChild(bar);
    personalInfo.append(text, progress);
}

export async function loadLeaderboardData() {
    loadController?.abort();
    loadController = new AbortController();
    const { signal } = loadController;
    showMessage('Leaderboard betöltése...');
    refreshLeaderboardBtn.disabled = true;

    try {
        if (state.modelType === 'my-votes') {
            const data = await requestJson(`/api/leaderboard/mine?model_type=${state.mySubType}`, { signal });
            state.personal = data;
            state.rows = data.leaderboard;
        } else {
            const data = await requestJson(`/api/leaderboard?model_type=${state.modelType}`, { signal });
            state.personal = null;
            state.rows = data;
            if (state.modelType === 'all') baseLeaderboard = data;
        }
        renderPersonalInfo();
        renderRows();
    } catch (error) {
        if (error.name === 'AbortError') return;
        if (error.status === 401) {
            showLoginPrompt();
            showMessage('A saját toplistához jelentkezz be.');
        } else {
            showMessage('Hiba a leaderboard betöltése közben.');
            showToast(error.message, 'danger');
        }
    } finally {
        if (!signal.aborted) refreshLeaderboardBtn.disabled = false;
    }
    if (!statsLoaded) loadStats();
}

async function loadStats() {
    statsLoaded = true;
    try {
        const stats = await requestJson('/api/leaderboard/stats');
        const updated = new Date(stats.method.computed_at).toLocaleString('hu-HU', { dateStyle: 'medium', timeStyle: 'short' });
        summaryLabel.textContent = `Bradley-Terry rangsor 95%-os konfidenciaintervallummal · ${formatNumber(stats.total_votes)} szavazat · frissítve: ${updated}`;
        document.querySelectorAll('[data-stat]').forEach((el) => {
            const value = stats.method[el.dataset.stat];
            if (value !== undefined) el.textContent = value;
        });
        window.APP_CONFIG.preliminary_threshold = stats.method.preliminary_threshold;

        const bias = stats.position_bias;
        const items = [
            ['Összes szavazat', formatNumber(stats.total_votes)],
            ['Döntetlen', formatNumber(stats.ties)],
            ['Mindkettő rossz', formatNumber(stats.both_bad)],
            ['Bejelentkezett szavazók', formatNumber(stats.voters)],
            ['Bal oldal nyerési aránya', bias.left_win_rate === null
                ? 'még nincs adat'
                : `${formatNumber(bias.left_win_rate, 1)}% (95% CI: ${formatNumber(bias.ci_lower, 1)}–${formatNumber(bias.ci_upper, 1)}%, n = ${formatNumber(bias.votes)})`],
        ];
        statsGrid.replaceChildren(...items.map(([label, value]) => {
            const item = document.createElement('div');
            item.className = 'leaderboard-stat';
            const dt = document.createElement('span');
            dt.className = 'leaderboard-stat-label';
            dt.textContent = label;
            const dd = document.createElement('strong');
            dd.textContent = value;
            item.append(dt, dd);
            return item;
        }));
        const note = document.createElement('p');
        note.className = 'leaderboard-stat-note';
        note.textContent = 'Az oldaltorzítás mérése: ha a bal oldali kép 50%-nál szignifikánsan többször nyer, a felhasználók a pozíció alapján is döntenek. A párosítás minden battle-nél véletlenszerűen osztja el az oldalakat.';
        statsGrid.appendChild(note);
    } catch (error) {
        statsLoaded = false;
        console.warn('Stats load failed:', error);
    }
}

// --- Minőség vs. ár ---

function median(values) {
    const sorted = [...values].sort((a, b) => a - b);
    const middle = Math.floor(sorted.length / 2);
    return sorted.length % 2 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2;
}

function getParetoModelIds(rows) {
    return new Set(rows.filter((candidate) => !rows.some((other) => (
        other.id !== candidate.id
        && other.price_per_1000 <= candidate.price_per_1000
        && other.score >= candidate.score
        && (other.price_per_1000 < candidate.price_per_1000 || other.score > candidate.score)
    ))).map((row) => row.id));
}

const qualityPriceQuadrants = {
    id: 'qualityPriceQuadrants',
    beforeDraw(chart, args, options) {
        const { ctx, chartArea, scales } = chart;
        if (!chartArea || !options?.priceThreshold || !options?.scoreThreshold) return;

        const thresholdX = scales.x.getPixelForValue(options.priceThreshold);
        const thresholdY = scales.y.getPixelForValue(options.scoreThreshold);
        const x = Math.min(Math.max(thresholdX, chartArea.left), chartArea.right);
        const y = Math.min(Math.max(thresholdY, chartArea.top), chartArea.bottom);

        ctx.save();
        ctx.fillStyle = options.goodColor;
        ctx.fillRect(chartArea.left, chartArea.top, x - chartArea.left, y - chartArea.top);
        ctx.fillStyle = options.badColor;
        ctx.fillRect(x, y, chartArea.right - x, chartArea.bottom - y);
        ctx.restore();
    }
};

const qualityPriceLabels = {
    id: 'qualityPriceLabels',
    afterDatasetsDraw(chart, args, options) {
        const { ctx, chartArea } = chart;
        if (!chartArea || chart.width < 720) return;

        const occupied = [];
        const candidates = [
            [12, -15], [12, 17], [-12, -15], [-12, 17],
            [18, 2], [-18, 2], [8, -28], [8, 30]
        ];

        ctx.save();
        ctx.font = '600 11px system-ui, sans-serif';
        ctx.textBaseline = 'middle';

        chart.data.datasets.forEach((dataset, datasetIndex) => {
            const meta = chart.getDatasetMeta(datasetIndex);
            meta.data.forEach((point, index) => {
                const label = dataset.data[index].name;
                const textWidth = ctx.measureText(label).width;
                let placement = null;

                for (const [dx, dy] of candidates) {
                    const alignRight = dx < 0;
                    const left = alignRight ? point.x + dx - textWidth : point.x + dx;
                    const box = { left: left - 3, right: left + textWidth + 3, top: point.y + dy - 8, bottom: point.y + dy + 8 };
                    const inside = box.left >= chartArea.left && box.right <= chartArea.right
                        && box.top >= chartArea.top && box.bottom <= chartArea.bottom;
                    const overlaps = occupied.some((used) => !(
                        box.right < used.left || box.left > used.right || box.bottom < used.top || box.top > used.bottom
                    ));
                    if (inside && !overlaps) {
                        placement = { dx, alignRight, box, dy };
                        break;
                    }
                }

                if (!placement) return;
                occupied.push(placement.box);
                ctx.fillStyle = options.labelBackground;
                ctx.fillRect(placement.box.left, placement.box.top,
                    placement.box.right - placement.box.left, placement.box.bottom - placement.box.top);
                ctx.textAlign = placement.alignRight ? 'right' : 'left';
                ctx.fillStyle = dataset.borderColor;
                ctx.fillText(label, point.x + placement.dx, point.y + placement.dy);
            });
        });
        ctx.restore();
    }
};

function destroyQualityPriceChart() {
    if (qualityPriceChart) {
        qualityPriceChart.destroy();
        qualityPriceChart = null;
    }
}

async function loadQualityPriceData() {
    if (!baseLeaderboard) {
        try {
            baseLeaderboard = await requestJson('/api/leaderboard?model_type=all');
        } catch (error) {
            showToast(error.message, 'danger');
            baseLeaderboard = null;
        }
    }

    const eligible = Array.isArray(baseLeaderboard)
        ? baseLeaderboard
            .filter((row) => Number.isFinite(row.price_per_1000) && row.price_per_1000 > 0)
            .sort((a, b) => b.score - a.score)
            .slice(0, state.qualityPriceLimit)
        : [];

    if (eligible.length < 2 || typeof window.Chart === 'undefined') {
        destroyQualityPriceChart();
        qualityPriceEmpty.hidden = false;
        return;
    }

    qualityPriceEmpty.hidden = true;
    renderQualityPriceChart(eligible);
}

function renderQualityPriceChart(rows) {
    destroyQualityPriceChart();
    const theme = chartTheme();

    const paretoIds = getParetoModelIds(rows);
    const toPoint = (row) => ({
        x: row.price_per_1000,
        y: row.score,
        id: row.id,
        name: row.name,
        display: row.display,
        pricing: row.pricing
    });
    const standard = rows.filter((row) => !paretoIds.has(row.id)).map(toPoint);
    const frontier = rows.filter((row) => paretoIds.has(row.id)).map(toPoint);
    const canvas = document.getElementById('quality-price-chart');

    qualityPriceChart = new window.Chart(canvas, {
        type: 'scatter',
        data: {
            datasets: [
                {
                    label: 'További modellek',
                    data: standard,
                    backgroundColor: theme.dark ? '#7fa7c1' : '#527b94',
                    borderColor: theme.dark ? '#a9c7da' : '#365a70',
                    pointRadius: 7,
                    pointHoverRadius: 10,
                    pointBorderWidth: 2
                },
                {
                    label: 'Pareto élvonal',
                    data: frontier,
                    backgroundColor: theme.dark ? '#3fb59b' : '#1f6f5f',
                    borderColor: theme.dark ? '#7fd8c3' : '#12473d',
                    pointRadius: 9,
                    pointHoverRadius: 12,
                    pointBorderWidth: 3
                }
            ]
        },
        plugins: [qualityPriceQuadrants, qualityPriceLabels],
        options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: { duration: theme.reducedMotion ? 0 : 650 },
            layout: { padding: { top: 16, right: 14 } },
            interaction: { mode: 'nearest', intersect: true },
            plugins: {
                legend: { display: false },
                qualityPriceQuadrants: {
                    priceThreshold: median(rows.map((row) => row.price_per_1000)),
                    scoreThreshold: median(rows.map((row) => row.score)),
                    goodColor: theme.dark ? 'rgba(63, 181, 155, 0.12)' : '#e4efdf',
                    badColor: theme.dark ? 'rgba(220, 110, 90, 0.12)' : '#f8e8e2',
                },
                qualityPriceLabels: { labelBackground: theme.dark ? 'rgba(33, 37, 41, 0.85)' : 'rgba(255, 255, 255, 0.82)' },
                tooltip: {
                    displayColors: false,
                    callbacks: {
                        title(items) {
                            return items[0]?.raw?.display || '';
                        },
                        label(context) {
                            return [
                                `Pontszám: ${formatNumber(context.raw.y)}`,
                                `Ár: $${context.raw.x.toLocaleString('hu-HU')} / 1 000 kép`,
                                `Forrásadat: ${context.raw.pricing}`
                            ];
                        },
                        afterLabel(context) {
                            return paretoIds.has(context.raw.id) ? 'Pareto élvonal' : '';
                        }
                    }
                }
            },
            scales: {
                x: {
                    type: 'logarithmic',
                    title: { display: true, text: 'API-ár (USD / 1 000 kép, logaritmikus)', font: { weight: 'bold' }, color: theme.text },
                    grid: { color: theme.grid },
                    ticks: { color: theme.muted, callback: (value) => `$${Number(value).toLocaleString('hu-HU')}` }
                },
                y: {
                    title: { display: true, text: 'Minőség (Arena pontszám)', font: { weight: 'bold' }, color: theme.text },
                    grace: '8%',
                    grid: { color: theme.grid },
                    ticks: { color: theme.muted }
                }
            }
        }
    });
}

// --- Párharc-mátrix ---

async function loadMatrixData() {
    matrixContainer.replaceChildren(Object.assign(document.createElement('p'), {
        className: 'text-center text-body-secondary py-4', textContent: 'Mátrix betöltése...'
    }));
    try {
        const modelType = state.modelType === 'my-votes' ? 'all' : state.modelType;
        matrixData = await requestJson(`/api/leaderboard/matrix?top=${state.matrixTop}&model_type=${modelType}`);
        renderMatrix();
    } catch (error) {
        matrixContainer.replaceChildren();
        showToast(error.message, 'danger');
    }
}

function matrixCellStyle(cell, metric, maxGames) {
    if (!cell) return '';
    if (metric === 'games') {
        const alpha = maxGames ? 0.08 + (cell.games / maxGames) * 0.72 : 0;
        return `background-color: rgba(13, 110, 253, ${alpha.toFixed(2)})`;
    }
    const value = metric === 'expected' ? cell.expected : cell.win_rate;
    if (value === null) return '';
    const distance = Math.min(Math.abs(value - 50) / 50, 1);
    const color = value >= 50 ? '25, 135, 84' : '220, 53, 69';
    return `background-color: rgba(${color}, ${(0.08 + distance * 0.7).toFixed(2)})`;
}

function renderMatrix() {
    if (!matrixData || matrixData.models.length < 2) {
        matrixContainer.replaceChildren(Object.assign(document.createElement('p'), {
            className: 'text-center text-body-secondary py-4', textContent: 'Még nincs elég adat a mátrixhoz.'
        }));
        return;
    }
    const metric = state.matrixMetric;
    const { models, cells } = matrixData;
    const maxGames = Math.max(...cells.flat().filter(Boolean).map((cell) => cell.games), 1);

    const table = document.createElement('table');
    table.className = 'matrix-table';
    const caption = document.createElement('caption');
    caption.className = 'visually-hidden';
    caption.textContent = 'Párharc-mátrix: a sor modelljének eredménye az oszlop modellje ellen';
    table.appendChild(caption);

    const thead = document.createElement('thead');
    const headRow = document.createElement('tr');
    const corner = document.createElement('th');
    corner.scope = 'col';
    corner.className = 'matrix-corner';
    corner.textContent = 'Sor ↓ / Oszlop →';
    headRow.appendChild(corner);
    models.forEach((model, index) => {
        const th = document.createElement('th');
        th.scope = 'col';
        th.className = 'matrix-col-head';
        th.title = model.display;
        th.textContent = String(index + 1);
        headRow.appendChild(th);
    });
    thead.appendChild(headRow);
    table.appendChild(thead);

    const tbody = document.createElement('tbody');
    models.forEach((rowModel, i) => {
        const tr = document.createElement('tr');
        const th = document.createElement('th');
        th.scope = 'row';
        th.className = 'matrix-row-head';
        th.textContent = `${i + 1}. ${rowModel.display}`;
        th.title = `${rowModel.display} – pontszám: ${formatNumber(rowModel.score)}`;
        tr.appendChild(th);
        models.forEach((colModel, j) => {
            const td = document.createElement('td');
            const cell = cells[i][j];
            if (!cell) {
                td.className = 'matrix-diagonal';
                td.setAttribute('aria-label', 'önmaga');
            } else {
                let text;
                if (metric === 'games') text = String(cell.games);
                else if (metric === 'expected') text = `${Math.round(cell.expected)}%`;
                else text = cell.win_rate === null ? '–' : `${Math.round(cell.win_rate)}%`;
                td.textContent = text;
                td.style.cssText = matrixCellStyle(cell, metric, maxGames);
                td.title = `${rowModel.display} vs. ${colModel.display}\n`
                    + `Győzelmi arány: ${cell.win_rate === null ? 'nincs meccs' : `${cell.win_rate}%`}\n`
                    + `Meccsek: ${cell.games}\nVárt (BT): ${cell.expected}%`;
            }
            tr.appendChild(td);
        });
        tbody.appendChild(tr);
    });
    table.appendChild(tbody);
    matrixContainer.replaceChildren(table);
}

// --- Nézetváltás és inicializálás ---

export function selectLeaderboardView(view) {
    if (!panels[view]) view = 'ranking';
    state.view = view;
    Object.entries(panels).forEach(([key, panel]) => { panel.hidden = key !== view; });
    viewCards.forEach((card) => {
        const selected = card.dataset.leaderboardView === view;
        card.classList.toggle('active', selected);
        card.setAttribute('aria-selected', String(selected));
        card.tabIndex = selected ? 0 : -1;
    });

    if (view === 'quality-price') requestAnimationFrame(loadQualityPriceData);
    if (view === 'matrix') loadMatrixData();
    document.dispatchEvent(new CustomEvent('leaderboard:viewchange', { detail: { view } }));
}

export function getLeaderboardView() {
    return state.view;
}

/** Téma váltásakor a diagramok színeit újra kell számolni. */
export function refreshLeaderboardCharts() {
    if (state.view === 'quality-price' && qualityPriceChart) loadQualityPriceData();
}

export function initLeaderboardMode() {
    loadVisibleColumns();
    populateProviders();
    updateSortHeaders();

    refreshLeaderboardBtn.addEventListener('click', async () => {
        baseLeaderboard = null;
        statsLoaded = false;
        await loadLeaderboardData();
        if (state.view === 'quality-price') loadQualityPriceData();
        if (state.view === 'matrix') loadMatrixData();
    });

    viewCards.forEach((card, index) => {
        card.addEventListener('click', () => selectLeaderboardView(card.dataset.leaderboardView));
        // Nyilakkal is lehessen a fülek között mozogni (WAI-ARIA tabs minta)
        card.addEventListener('keydown', (event) => {
            if (!['ArrowRight', 'ArrowLeft', 'ArrowDown', 'ArrowUp'].includes(event.key)) return;
            event.preventDefault();
            const delta = event.key === 'ArrowRight' || event.key === 'ArrowDown' ? 1 : -1;
            const next = viewCards[(index + delta + viewCards.length) % viewCards.length];
            next.focus();
            selectLeaderboardView(next.dataset.leaderboardView);
        });
    });

    qualityPriceLimitRadios.forEach((radio) => {
        radio.addEventListener('change', (event) => {
            state.qualityPriceLimit = Number(event.target.value);
            loadQualityPriceData();
        });
    });

    modelTypeRadios.forEach((radio) => {
        radio.addEventListener('change', (event) => {
            state.modelType = event.target.value;
            myVotesSubfilter.style.display = state.modelType === 'my-votes' ? 'flex' : 'none';
            loadLeaderboardData();
            if (state.view === 'matrix') loadMatrixData();
        });
    });

    myTypeRadios.forEach((radio) => {
        radio.addEventListener('change', (event) => {
            state.mySubType = event.target.value;
            loadLeaderboardData();
        });
    });

    columnToggles.forEach((toggle) => {
        toggle.addEventListener('change', (event) => {
            const { column } = event.target.dataset;
            if (event.target.checked) state.visibleColumns.add(column);
            else state.visibleColumns.delete(column);
            saveVisibleColumns();
            updateColumnVisibility();
            renderRows(); // Nem kell újra lekérni az adatokat
        });
    });

    sortHeaders.forEach((th) => {
        th.querySelector('.sort-btn')?.addEventListener('click', () => {
            const key = th.dataset.sort;
            state.sort = state.sort.key === key
                ? { key, direction: state.sort.direction === 'asc' ? 'desc' : 'asc' }
                : { key, direction: SORT_DEFAULT_DIRECTION[key] || 'desc' };
            updateSortHeaders();
            renderRows();
        });
    });

    let searchTimer = null;
    searchInput.addEventListener('input', () => {
        clearTimeout(searchTimer);
        searchTimer = setTimeout(() => {
            state.search = searchInput.value;
            renderRows();
        }, 120);
    });
    providerSelect.addEventListener('change', () => {
        state.provider = providerSelect.value;
        renderRows();
    });
    hidePreliminaryToggle.addEventListener('change', () => {
        state.hidePreliminary = hidePreliminaryToggle.checked;
        renderRows();
    });

    matrixMetricRadios.forEach((radio) => {
        radio.addEventListener('change', (event) => {
            state.matrixMetric = event.target.value;
            renderMatrix();
        });
    });
    matrixTopSelect.addEventListener('change', () => {
        state.matrixTop = Number(matrixTopSelect.value);
        loadMatrixData();
    });

    methodDetails.addEventListener('toggle', () => {
        if (methodDetails.open && !statsLoaded) loadStats();
    });
}
