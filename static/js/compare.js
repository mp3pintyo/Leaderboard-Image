import { createVideoLink } from './videoLink.js';
import { requestJson } from './api.js';
import { showToast } from './toast.js';
import { chartTheme } from './theme.js';
import { bindLightbox } from './lightbox.js';

// DOM elemek
const compareModel1Select = document.getElementById('compare-model1-select');
const compareModel2Select = document.getElementById('compare-model2-select');
const compareBtn = document.getElementById('compare-load-btn');
const swapBtn = document.getElementById('compare-swap-btn');
const compareResultDiv = document.getElementById('compare-result');

let promptChart = null;
let lastData = null;
let requestSeq = 0;

const TAG_LABELS = {
    photorealistic: 'fotorealisztikus',
    artistic: 'művészi',
    general: 'általános',
    multimodal: 'multimodális',
    'text-rendering': 'szövegírás',
    editing: 'szerkesztés',
    inpainting: 'inpainting',
    stylized: 'stilizált',
    lightweight: 'könnyű',
    fast: 'gyors',
    'high-resolution': 'nagy felbontás',
    'commercial-safe': 'kereskedelmileg biztonságos',
    flexible: 'rugalmas',
};

const SPEED_LABELS = { fast: '⚡ Gyors', medium: '⏱ Közepes', slow: '🐢 Lassú' };

function el(tag, options = {}, children = []) {
    const element = document.createElement(tag);
    Object.entries(options).forEach(([key, value]) => {
        if (key === 'className') element.className = value;
        else if (key === 'text') element.textContent = value;
        else if (key === 'dataset') Object.assign(element.dataset, value);
        else element.setAttribute(key, value);
    });
    (Array.isArray(children) ? children : [children]).filter(Boolean).forEach((child) => {
        element.append(child instanceof Node ? child : document.createTextNode(String(child)));
    });
    return element;
}

function safeHttpUrl(url) {
    try {
        const parsed = new URL(String(url), window.location.origin);
        return ['http:', 'https:'].includes(parsed.protocol) ? parsed.href : null;
    } catch {
        return null;
    }
}

function formatNumber(value, digits = 0) {
    return Number(value).toLocaleString('hu-HU', { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

function renderModelCard(model, side) {
    const website = safeHttpUrl(model.website);
    const rows = [
        ['Szolgáltató', model.provider || 'N/A'],
        ['Licenc', el('span', { className: `badge ${model.open_source ? 'text-bg-success' : 'text-bg-warning'}`, text: model.open_source ? 'Open Source' : 'Zárt forrású' })],
        ['Kategória', model.type || 'N/A'],
        ['Megjelenés', model.release_date || 'N/A'],
        ['Max felbontás', model.max_resolution || 'N/A'],
        ['Árazás', model.pricing || 'N/A'],
        ['API', el('span', { className: `badge ${model.api_available ? 'text-bg-success' : 'text-bg-secondary'}`, text: model.api_available ? 'Elérhető' : 'Nem elérhető' })],
        ['Sebesség', SPEED_LABELS[model.speed] || 'N/A'],
        ['Videó', createVideoLink(model)],
        ['Weboldal', website
            ? el('a', { href: website, target: '_blank', rel: 'noopener noreferrer', text: website.replace(/^https?:\/\//, '').replace(/\/$/, '') })
            : 'N/A'],
        ['Címkék', (model.tags || []).length
            ? el('span', { className: 'd-flex flex-wrap gap-1' }, model.tags.map((tag) => el('span', { className: 'badge text-bg-light border', text: TAG_LABELS[tag] || tag })))
            : 'Nincs'],
    ];
    const dl = el('dl');
    rows.forEach(([label, value]) => dl.append(el('dt', { text: label }), el('dd', {}, value)));
    return el('article', { className: `compare-panel compare-model-card compare-model-${side}` }, [
        el('h3', { text: model.display }),
        dl,
    ]);
}

function metricRow(label, a, b, { format, baseline = 0, higherIsBetter = true, noteA = '', noteB = '', missingA = false, missingB = false }) {
    const max = Math.max(missingA ? 0 : a - baseline, missingB ? 0 : b - baseline, 1);
    const side = (value, note, cls, leading, missing) => {
        const bar = el('span', { className: 'compare-metric-bar', 'aria-hidden': 'true' },
            missing ? null : el('span', { className: 'compare-metric-fill', style: `width: ${Math.max(2, ((value - baseline) / max) * 100)}%` }));
        const valueEl = el('span', { className: `compare-metric-value${leading ? ' is-leading' : ''}` },
            missing ? ['–', el('small', { text: 'nincs még adat' })] : [format(value), note ? el('small', { text: note }) : null]);
        return el('div', { className: `compare-metric-side ${cls}` }, [valueEl, bar]);
    };
    // Adat nélküli modellel nincs értelme „vezetőt” jelölni
    const comparable = !missingA && !missingB;
    const aLeads = comparable && (higherIsBetter ? a > b : a < b);
    const bLeads = comparable && (higherIsBetter ? b > a : b < a);
    return el('div', { className: 'compare-metric' }, [
        el('div', { className: 'compare-model-a' }, side(a, noteA, 'side-a', aLeads, missingA)),
        el('div', { className: 'compare-metric-label', text: label }),
        el('div', { className: 'compare-model-b' }, side(b, noteB, 'side-b', bLeads, missingB)),
    ]);
}

/** Helyezés sor: „6. hely”, alatta a lehetséges helyezéssáv; a sáv hossza a helyezéssel arányos. */
function rankRow(m1, m2) {
    const side = (model, cls, leading) => {
        const total = model.ranked_models || 1;
        const hasRank = model.position !== null && model.position !== undefined;
        const note = !hasRank ? 'nincs még adat'
            : model.rank !== model.rank_worst ? `lehetséges: ${model.rank}–${model.rank_worst}. · ${total} modellből`
                : `${total} modellből`;
        const valueEl = el('span', { className: `compare-metric-value${leading ? ' is-leading' : ''}` },
            [hasRank ? `${model.position}. hely` : '–', el('small', { text: note })]);
        const bar = el('span', { className: 'compare-metric-bar', 'aria-hidden': 'true' },
            hasRank ? el('span', { className: 'compare-metric-fill', style: `width: ${Math.max(2, ((total - model.position + 1) / total) * 100)}%` }) : null);
        return el('div', { className: `compare-metric-side ${cls}` }, [valueEl, bar]);
    };
    const comparable = m1.position && m2.position;
    return el('div', { className: 'compare-metric' }, [
        el('div', { className: 'compare-model-a' }, side(m1, 'side-a', comparable && m1.position < m2.position)),
        el('div', { className: 'compare-metric-label', text: 'Helyezés' }),
        el('div', { className: 'compare-model-b' }, side(m2, 'side-b', comparable && m2.position < m1.position)),
    ]);
}

function ciNote(model) {
    if (model.ci_lower === null || model.ci_lower === undefined) return 'nincs adat';
    return `95% CI: ${formatNumber(model.ci_lower)}–${formatNumber(model.ci_upper)}${model.preliminary ? ' · előzetes' : ''}`;
}

function renderStats(stats) {
    const m1 = stats.model1;
    const m2 = stats.model2;
    const h2h = stats.head_to_head;

    const header = el('div', { className: 'compare-metric' }, [
        el('strong', { className: 'text-end compare-model-a', style: 'color: var(--model-color)', text: m1.display }),
        el('span', { className: 'compare-metric-label', text: 'vs.' }),
        el('strong', { className: 'compare-model-b', style: 'color: var(--model-color)', text: m2.display }),
    ]);

    const noData = { missingA: m1.matches === 0, missingB: m2.matches === 0 };
    const metrics = [
        rankRow(m1, m2),
        metricRow('Arena pontszám', m1.score, m2.score, { format: (v) => formatNumber(v), baseline: 1000, noteA: ciNote(m1), noteB: ciNote(m2), ...noData }),
        metricRow('Győzelmi arány', m1.win_rate, m2.win_rate, { format: (v) => `${formatNumber(v, 1)}%`, ...noData }),
        metricRow('Meccsek', m1.matches, m2.matches, {
            format: (v) => formatNumber(v),
            noteA: `${m1.wins} győzelem · ${m1.ties} döntetlen`, noteB: `${m2.wins} győzelem · ${m2.ties} döntetlen`,
        }),
    ];

    let h2hContent;
    if (h2h.total > 0) {
        const pct = (value) => (value / h2h.total) * 100;
        const segment = (cls, value, text) => value > 0
            ? el('span', { className: cls, style: `width: ${pct(value)}%`, title: text }, pct(value) >= 12 ? text : '')
            : null;
        h2hContent = [
            el('div', { className: 'compare-h2h', role: 'img', 'aria-label': `${m1.display}: ${h2h.model1_wins} győzelem, döntetlen: ${h2h.ties}, ${m2.display}: ${h2h.model2_wins} győzelem` }, [
                segment('h2h-a', h2h.model1_wins, `${h2h.model1_wins} (${Math.round(pct(h2h.model1_wins))}%)`),
                segment('h2h-tie', h2h.ties, `${h2h.ties} döntetlen`),
                segment('h2h-b', h2h.model2_wins, `${h2h.model2_wins} (${Math.round(pct(h2h.model2_wins))}%)`),
            ]),
            el('p', { className: 'small text-body-secondary mt-2 mb-0', text: `${m1.display}: ${h2h.model1_wins} · döntetlen: ${h2h.ties} · ${m2.display}: ${h2h.model2_wins}` }),
        ];
    } else {
        h2hContent = el('p', { className: 'text-body-secondary mb-0', text: 'Még nem kerültek egymás ellen.' });
    }

    return el('section', { className: 'compare-panel' }, [
        el('h3', { text: 'Összesített statisztikák' }),
        header,
        ...metrics,
        el('h3', { className: 'mt-4', text: `Egymás ellen (${h2h.total} meccs)` }),
        ...[].concat(h2hContent),
    ]);
}

function renderPromptChartPanel(stats) {
    const relevant = stats.prompt_stats.filter((p) => p.model1.matches > 0 || p.model2.matches > 0);
    if (!relevant.length) return null;
    return el('section', { className: 'compare-panel' }, [
        el('h3', { text: 'Győzelmi arány promptonként' }),
        el('div', { className: 'chart-container', style: `position: relative; height: ${Math.max(260, relevant.length * 34)}px; width: 100%;` },
            el('canvas', { id: 'compare-bar-chart', role: 'img', 'aria-label': 'A két modell győzelmi aránya promptonként' })),
    ]);
}

function createPromptChart(stats) {
    const canvas = document.getElementById('compare-bar-chart');
    if (!canvas || typeof window.Chart === 'undefined') return;
    const relevant = stats.prompt_stats.filter((p) => p.model1.matches > 0 || p.model2.matches > 0);
    const theme = chartTheme();
    const styles = getComputedStyle(document.body);
    const colorA = styles.getPropertyValue('--model-a-color').trim() || '#0d6efd';
    const colorB = styles.getPropertyValue('--model-b-color').trim() || '#198754';

    promptChart = new window.Chart(canvas, {
        type: 'bar',
        data: {
            labels: relevant.map((p) => p.prompt_id),
            datasets: [
                { label: stats.model1.display, data: relevant.map((p) => p.model1.win_rate), backgroundColor: colorA, borderRadius: 4 },
                { label: stats.model2.display, data: relevant.map((p) => p.model2.win_rate), backgroundColor: colorB, borderRadius: 4 },
            ],
        },
        options: {
            indexAxis: 'y',
            responsive: true,
            maintainAspectRatio: false,
            animation: { duration: theme.reducedMotion ? 0 : 500 },
            scales: {
                x: { beginAtZero: true, max: 100, title: { display: true, text: 'Győzelmi arány (%)', color: theme.text }, grid: { color: theme.grid }, ticks: { color: theme.muted } },
                y: { title: { display: true, text: 'Prompt', color: theme.text }, grid: { color: theme.grid }, ticks: { color: theme.muted } },
            },
            plugins: {
                legend: { position: 'top', labels: { color: theme.text } },
                tooltip: {
                    callbacks: {
                        title: (items) => {
                            const prompt = relevant[items[0].dataIndex];
                            return `${prompt.prompt_id}: ${prompt.prompt_text}`;
                        },
                        label: (ctx) => {
                            const entry = relevant[ctx.dataIndex][ctx.datasetIndex === 0 ? 'model1' : 'model2'];
                            return `${ctx.dataset.label}: ${ctx.raw}% (${entry.wins} gy. / ${entry.matches} meccs)`;
                        },
                    },
                },
            },
        },
    });
}

function renderPromptTable(stats, model1Id, model2Id) {
    const table = el('table', { className: 'table table-sm align-middle mb-0 compare-prompt-table' });
    table.append(el('thead', {}, el('tr', {}, [
        el('th', { scope: 'col', text: 'Prompt' }),
        el('th', { scope: 'col', className: 'compare-model-a', style: 'color: var(--model-color)', text: stats.model1.display }),
        el('th', { scope: 'col', className: 'compare-model-b', style: 'color: var(--model-color)', text: stats.model2.display }),
    ])));
    const tbody = el('tbody');

    stats.prompt_stats.forEach((prompt) => {
        const detailsId = `compare-images-${prompt.prompt_id}`;
        const toggle = el('button', {
            type: 'button', className: 'compare-prompt-toggle', 'aria-expanded': 'false', 'aria-controls': detailsId,
            title: 'Képek megjelenítése',
        }, [el('span', { className: 'fw-semibold', text: prompt.prompt_id }), el('span', { className: 'small text-body-secondary', text: prompt.prompt_text })]);

        const cell = (entry, side) => el('td', { className: `compare-model-${side} text-nowrap` }, [
            `${entry.wins}/${entry.matches}`,
            entry.ties ? el('small', { className: 'text-body-secondary', text: ` (+${entry.ties} d.)` }) : null,
            el('span', { className: 'compare-mini-bar', 'aria-hidden': 'true' }, el('span', { style: `width: ${entry.win_rate}%` })),
        ]);

        const row = el('tr', { className: 'compare-prompt-row' }, [el('td', {}, toggle), cell(prompt.model1, 'a'), cell(prompt.model2, 'b')]);
        const detailsCell = el('td', { colspan: '3' });
        const detailsRow = el('tr', { id: detailsId, hidden: '' }, detailsCell);

        toggle.addEventListener('click', async () => {
            const open = toggle.getAttribute('aria-expanded') === 'true';
            toggle.setAttribute('aria-expanded', String(!open));
            detailsRow.hidden = open;
            if (open || detailsCell.dataset.loaded === 'true') return;
            detailsCell.replaceChildren(el('p', { className: 'text-center py-3 mb-0' }, [
                el('span', { className: 'spinner-border spinner-border-sm me-2', role: 'status' }), 'Képek betöltése...',
            ]));
            const fetchImage = (modelId) => requestJson(`/api/get_image?model=${encodeURIComponent(modelId)}&prompt_id=${encodeURIComponent(prompt.prompt_id)}`)
                .then((data) => safeHttpUrl(data.image_url)).catch(() => null);
            const [url1, url2] = await Promise.all([fetchImage(model1Id), fetchImage(model2Id)]);
            const figure = (url, model, side) => el('figure', { className: `compare-model-${side}` }, [
                el('figcaption', { text: model.display }),
                url
                    ? el('img', { src: url, alt: `${model.display} képe – prompt ${prompt.prompt_id}`, className: 'compare-prompt-img', loading: 'lazy', decoding: 'async' })
                    : el('p', { className: 'text-body-secondary py-3', text: 'Kép nem elérhető' }),
            ]);
            const grid = el('div', { className: 'compare-prompt-images' }, [figure(url1, stats.model1, 'a'), figure(url2, stats.model2, 'b')]);
            detailsCell.replaceChildren(grid);
            detailsCell.dataset.loaded = 'true';
            bindLightbox(grid.querySelectorAll('img'), (img) => `${img.alt}`);
        });

        tbody.append(row, detailsRow);
    });
    table.append(tbody);

    return el('section', { className: 'compare-panel' }, [
        el('h3', {}, ['Prompt szintű eredmények ', el('small', { className: 'fw-normal text-body-secondary', text: '(kattints egy promptra a képekhez)' })]),
        el('div', { className: 'table-responsive' }, table),
    ]);
}

function destroyCharts() {
    if (promptChart) {
        promptChart.destroy();
        promptChart = null;
    }
}

function updateRoute(model1Id, model2Id) {
    const hash = `#/compare?a=${encodeURIComponent(model1Id)}&b=${encodeURIComponent(model2Id)}`;
    if (window.location.hash !== hash) history.replaceState(null, '', hash);
    document.dispatchEvent(new CustomEvent('route:replaced'));
}

export async function loadCompareData() {
    const model1Id = compareModel1Select.value;
    const model2Id = compareModel2Select.value;

    if (model1Id === model2Id) {
        showToast('Válassz két különböző modellt!', 'warning');
        return;
    }
    updateRoute(model1Id, model2Id);

    const seq = ++requestSeq;
    compareBtn.disabled = true;
    compareResultDiv.setAttribute('aria-busy', 'true');
    try {
        const [infoData, statsData] = await Promise.all([
            requestJson(`/api/model_info?model1=${encodeURIComponent(model1Id)}&model2=${encodeURIComponent(model2Id)}`),
            requestJson(`/api/compare_stats?model1=${encodeURIComponent(model1Id)}&model2=${encodeURIComponent(model2Id)}`),
        ]);
        if (seq !== requestSeq) return;
        lastData = { infoData, statsData, model1Id, model2Id };
        render();
    } catch (error) {
        if (seq === requestSeq) {
            compareResultDiv.replaceChildren(el('div', { className: 'alert alert-danger', text: 'Hiba az adatok betöltése közben.' }));
            showToast(error.message, 'danger');
        }
    } finally {
        if (seq === requestSeq) {
            compareBtn.disabled = false;
            compareResultDiv.removeAttribute('aria-busy');
        }
    }
}

function render() {
    if (!lastData) return;
    const { infoData, statsData, model1Id, model2Id } = lastData;
    destroyCharts();
    compareResultDiv.replaceChildren(
        el('div', { className: 'row g-3 mb-2' }, [
            el('div', { className: 'col-md-6' }, renderModelCard(infoData.model1, 'a')),
            el('div', { className: 'col-md-6' }, renderModelCard(infoData.model2, 'b')),
        ]),
        renderStats(statsData),
        renderPromptChartPanel(statsData) || '',
        renderPromptTable(statsData, model1Id, model2Id),
    );
    createPromptChart(statsData);
}

/** Téma váltásakor a diagram színeit újra kell számolni. */
export function refreshCompareCharts() {
    if (promptChart && lastData) {
        destroyCharts();
        createPromptChart(lastData.statsData);
    }
}

/** Útvonalból (#/compare?a=...&b=...) érkező modellek beállítása és betöltése. */
export function applyCompareRoute(params) {
    const a = params.get('a');
    const b = params.get('b');
    const valid = (id) => id && [...compareModel1Select.options].some((option) => option.value === id);
    if (valid(a) && valid(b) && a !== b) {
        const changed = compareModel1Select.value !== a || compareModel2Select.value !== b || !lastData;
        compareModel1Select.value = a;
        compareModel2Select.value = b;
        if (changed) loadCompareData();
    }
}

export function initCompareMode() {
    compareBtn.addEventListener('click', loadCompareData);
    swapBtn?.addEventListener('click', () => {
        const first = compareModel1Select.value;
        compareModel1Select.value = compareModel2Select.value;
        compareModel2Select.value = first;
        loadCompareData();
    });

    // Alapértelmezésben a második legördülő egy másik modellt mutasson
    if (compareModel2Select.options.length > 1 && compareModel2Select.value === compareModel1Select.value) {
        compareModel2Select.selectedIndex = 1;
    }
}
