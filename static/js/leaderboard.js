import { fetchData } from './api.js';

const leaderboardTableBody = document.getElementById('leaderboard-table-body');
const refreshLeaderboardBtn = document.getElementById('refresh-leaderboard-btn');
const modelTypeRadios = document.querySelectorAll('input[name="model-type"]');
const myVotesSubfilter = document.getElementById('my-votes-subfilter');
const myTypeRadios = document.querySelectorAll('input[name="my-type"]');
const viewCards = document.querySelectorAll('[data-leaderboard-view]');
const rankingPanel = document.getElementById('leaderboard-ranking-panel');
const qualityPricePanel = document.getElementById('leaderboard-quality-price-panel');
const qualityPriceLimitRadios = document.querySelectorAll('input[name="quality-price-limit"]');
const qualityPriceEmpty = document.getElementById('quality-price-empty');

let currentModelType = 'all';
let currentMySubType = 'all';
let currentQualityPriceLimit = 10;
let baseLeaderboard = null;
let qualityPriceChart = null;

function renderRows(rows) {
    leaderboardTableBody.innerHTML = '';
    if (rows.length === 0) {
        leaderboardTableBody.innerHTML = '<tr><td colspan="7" class="text-center">Nincs adat a kiválasztott szűrésre</td></tr>';
        return;
    }

    const createCell = (text, strong = false) => {
        const td = document.createElement('td');
        if (strong) {
            const strongEl = document.createElement('strong');
            strongEl.textContent = text;
            td.appendChild(strongEl);
        } else {
            td.textContent = text;
        }
        return td;
    };

    const createBadge = (text, className, title = '') => {
        const badge = document.createElement('span');
        badge.className = `badge ${className}`;
        badge.textContent = text;
        if (title) badge.title = title;
        return badge;
    };

    rows.forEach((row, index) => {
        const tr = document.createElement('tr');
        if (row.frozen) tr.classList.add('frozen-model');
        const modelDisplayName = row.display || (row.provider ? `${row.provider}: ${row.name}` : row.name);

        tr.appendChild(createCell(String(index + 1)));

        const modelTd = document.createElement('td');
        modelTd.append(document.createTextNode(modelDisplayName));
        if (row.frozen) {
            modelTd.append(document.createTextNode(' '));
            modelTd.append(createBadge('Befagyasztva', 'bg-secondary', 'Ez a modell jelenleg ki van zárva az Arena Battle-ből'));
        }
        tr.appendChild(modelTd);

        tr.appendChild(createCell(String(row.elo), true));
        tr.appendChild(createCell(String(row.wins)));
        tr.appendChild(createCell(String(row.matches)));
        tr.appendChild(createCell(`${row.win_rate}%`));

        const typeTd = document.createElement('td');
        typeTd.appendChild(
            row.open_source
                ? createBadge('Open Source', 'bg-success')
                : createBadge('Zárt forrású', 'bg-warning text-dark')
        );
        tr.appendChild(typeTd);

        leaderboardTableBody.appendChild(tr);
    });
}

function median(values) {
    const sorted = [...values].sort((a, b) => a - b);
    const middle = Math.floor(sorted.length / 2);
    return sorted.length % 2 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2;
}

function getParetoModelIds(rows) {
    return new Set(rows.filter((candidate) => !rows.some((other) => (
        other.id !== candidate.id
        && other.price_per_1000 <= candidate.price_per_1000
        && other.elo >= candidate.elo
        && (other.price_per_1000 < candidate.price_per_1000 || other.elo > candidate.elo)
    ))).map((row) => row.id));
}

const qualityPriceQuadrants = {
    id: 'qualityPriceQuadrants',
    beforeDraw(chart, args, options) {
        const { ctx, chartArea, scales } = chart;
        if (!chartArea || !options?.priceThreshold || !options?.eloThreshold) return;

        const thresholdX = scales.x.getPixelForValue(options.priceThreshold);
        const thresholdY = scales.y.getPixelForValue(options.eloThreshold);
        const x = Math.min(Math.max(thresholdX, chartArea.left), chartArea.right);
        const y = Math.min(Math.max(thresholdY, chartArea.top), chartArea.bottom);

        ctx.save();
        ctx.fillStyle = '#e4efdf';
        ctx.fillRect(chartArea.left, chartArea.top, x - chartArea.left, y - chartArea.top);
        ctx.fillStyle = '#f8e8e2';
        ctx.fillRect(x, y, chartArea.right - x, chartArea.bottom - y);
        ctx.restore();
    }
};

const qualityPriceLabels = {
    id: 'qualityPriceLabels',
    afterDatasetsDraw(chart) {
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
                const raw = dataset.data[index];
                const label = raw.name;
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
                        placement = { dx, dy, alignRight, box };
                        break;
                    }
                }

                if (!placement) return;
                occupied.push(placement.box);
                ctx.fillStyle = 'rgba(255, 255, 255, 0.82)';
                ctx.fillRect(
                    placement.box.left,
                    placement.box.top,
                    placement.box.right - placement.box.left,
                    placement.box.bottom - placement.box.top
                );
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
        baseLeaderboard = await fetchData('/api/leaderboard?model_type=all');
    }

    const eligible = Array.isArray(baseLeaderboard)
        ? baseLeaderboard
            .filter((row) => Number.isFinite(row.price_per_1000))
            .sort((a, b) => b.elo - a.elo)
            .slice(0, currentQualityPriceLimit)
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

    const paretoIds = getParetoModelIds(rows);
    const toPoint = (row) => ({
        x: row.price_per_1000,
        y: row.elo,
        id: row.id,
        name: row.name,
        display: row.display,
        pricing: row.pricing
    });
    const standard = rows.filter((row) => !paretoIds.has(row.id)).map(toPoint);
    const frontier = rows.filter((row) => paretoIds.has(row.id)).map(toPoint);
    const prices = rows.map((row) => row.price_per_1000);
    const elos = rows.map((row) => row.elo);
    const priceThreshold = median(prices);
    const eloThreshold = median(elos);
    const canvas = document.getElementById('quality-price-chart');

    qualityPriceChart = new window.Chart(canvas, {
        type: 'scatter',
        data: {
            datasets: [
                {
                    label: 'További modellek',
                    data: standard,
                    backgroundColor: '#527b94',
                    borderColor: '#365a70',
                    pointRadius: 7,
                    pointHoverRadius: 10,
                    pointBorderWidth: 2
                },
                {
                    label: 'Pareto élvonal',
                    data: frontier,
                    backgroundColor: '#1f6f5f',
                    borderColor: '#12473d',
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
            animation: {
                duration: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 0 : 650
            },
            layout: {
                padding: { top: 16, right: 14 }
            },
            interaction: {
                mode: 'nearest',
                intersect: true
            },
            plugins: {
                legend: { display: false },
                qualityPriceQuadrants: { priceThreshold, eloThreshold },
                tooltip: {
                    displayColors: false,
                    callbacks: {
                        title(items) {
                            return items[0]?.raw?.display || '';
                        },
                        label(context) {
                            return [
                                `ELO: ${context.raw.y}`,
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
                    beginAtZero: true,
                    title: {
                        display: true,
                        text: 'API-ár (USD / 1 000 kép)',
                        font: { weight: 'bold' }
                    },
                    grid: { color: 'rgba(70, 82, 90, 0.12)' },
                    ticks: {
                        callback(value) {
                            return `$${value}`;
                        }
                    }
                },
                y: {
                    title: {
                        display: true,
                        text: 'Minőség (ELO)',
                        font: { weight: 'bold' }
                    },
                    grace: '8%',
                    grid: { color: 'rgba(70, 82, 90, 0.12)' }
                }
            }
        }
    });
}

function selectLeaderboardView(view) {
    const showQualityPrice = view === 'quality-price';
    rankingPanel.hidden = showQualityPrice;
    qualityPricePanel.hidden = !showQualityPrice;

    viewCards.forEach((card) => {
        const selected = card.dataset.leaderboardView === view;
        card.classList.toggle('active', selected);
        card.setAttribute('aria-selected', String(selected));
    });

    if (showQualityPrice) {
        requestAnimationFrame(loadQualityPriceData);
    }
}

export async function loadLeaderboardData() {
    leaderboardTableBody.innerHTML = '<tr><td colspan="7" class="text-center">Leaderboard betöltése...</td></tr>';
    refreshLeaderboardBtn.disabled = true;

    let infoBar = document.getElementById('personal-leaderboard-info');

    if (currentModelType === 'my-votes') {
        const data = await fetchData(`/api/leaderboard/mine?model_type=${currentMySubType}`);
        if (data) {
            if (!infoBar) {
                infoBar = document.createElement('div');
                infoBar.id = 'personal-leaderboard-info';
                infoBar.className = 'alert alert-info text-center mb-3';
                leaderboardTableBody.closest('.table-responsive').before(infoBar);
            }
            infoBar.textContent = data.vote_count === 0
                ? 'Még nem adtál le szavazatot. Szavazz az Arena Battle módban, hogy megjelenjen a saját toplistád!'
                : `A toplista a te ${data.vote_count} szavazatod alapján lett kiszámítva.`;
            renderRows(data.leaderboard);
        } else {
            leaderboardTableBody.innerHTML = '<tr><td colspan="7" class="text-center">Hiba a leaderboard betöltése közben.</td></tr>';
        }
    } else {
        if (infoBar) infoBar.remove();

        const data = await fetchData(`/api/leaderboard?model_type=${currentModelType}`);
        if (data) {
            if (currentModelType === 'all') baseLeaderboard = data;
            renderRows(data);
        } else {
            leaderboardTableBody.innerHTML = '<tr><td colspan="7" class="text-center">Hiba a leaderboard betöltése közben.</td></tr>';
        }
    }

    refreshLeaderboardBtn.disabled = false;
}

export function initLeaderboardMode() {
    refreshLeaderboardBtn.addEventListener('click', async () => {
        baseLeaderboard = null;
        await loadLeaderboardData();
        if (!qualityPricePanel.hidden) loadQualityPriceData();
    });

    viewCards.forEach((card) => {
        card.addEventListener('click', () => selectLeaderboardView(card.dataset.leaderboardView));
    });

    qualityPriceLimitRadios.forEach((radio) => {
        radio.addEventListener('change', (event) => {
            currentQualityPriceLimit = Number(event.target.value);
            loadQualityPriceData();
        });
    });

    modelTypeRadios.forEach((radio) => {
        radio.addEventListener('change', (event) => {
            currentModelType = event.target.value;
            myVotesSubfilter.style.display = currentModelType === 'my-votes' ? 'flex' : 'none';
            loadLeaderboardData();
        });
    });

    myTypeRadios.forEach((radio) => {
        radio.addEventListener('change', (event) => {
            currentMySubType = event.target.value;
            loadLeaderboardData();
        });
    });
}
