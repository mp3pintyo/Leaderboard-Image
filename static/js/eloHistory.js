import { requestJson } from './api.js';
import { colorPalette } from './config.js';
import { chartTheme } from './theme.js';
import { showToast } from './toast.js';

const eloHistoryChartCanvas = document.getElementById('eloHistoryChart');
const refreshHistoryBtn = document.getElementById('refresh-history-btn');
const topNSlider = document.getElementById('top-n-slider');
const topNValue = document.getElementById('top-n-value');
const emptyMessage = document.getElementById('elo-history-empty');

let eloHistoryChart = null;
let eloHistoryRange = 'all';
let topNCount = Number(topNSlider?.value) || 10;
let loadController = null;
let lastSeries = null;

function withAlpha(hex, alpha) {
    const value = hex.replace('#', '');
    const r = parseInt(value.substring(0, 2), 16);
    const g = parseInt(value.substring(2, 4), 16);
    const b = parseInt(value.substring(4, 6), 16);
    return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

function timeUnitFor(range) {
    if (range === '1w' || range === '2w') return 'day';
    if (range === '1m' || range === '3m') return 'week';
    return 'month';
}

export async function loadEloHistoryData() {
    loadController?.abort();
    loadController = new AbortController();
    refreshHistoryBtn.disabled = true;
    try {
        const data = await requestJson(`/api/elo_history?range=${eloHistoryRange}&top=${topNCount}`, { signal: loadController.signal });
        if (topNSlider && data.models_total) topNSlider.max = String(Math.min(30, data.models_total));
        lastSeries = data.series;
        renderEloHistoryChart(data.series);
    } catch (error) {
        if (error.name === 'AbortError') return;
        showToast(error.message, 'danger');
    } finally {
        refreshHistoryBtn.disabled = false;
    }
}

function highlightDataset(chart, activeIndex) {
    chart.data.datasets.forEach((dataset, index) => {
        const base = dataset.baseColor;
        const faded = activeIndex !== null && index !== activeIndex;
        dataset.borderColor = faded ? withAlpha(base, 0.12) : base;
        dataset.backgroundColor = faded ? withAlpha(base, 0.12) : base;
        dataset.borderWidth = activeIndex === index ? 3.5 : 2;
    });
    chart.update('none');
}

function renderEloHistoryChart(series) {
    if (eloHistoryChart) {
        eloHistoryChart.destroy();
        eloHistoryChart = null;
    }
    const withPoints = series.filter((entry) => entry.points.length > 0);
    emptyMessage.hidden = withPoints.length > 0;
    if (!withPoints.length) return;

    const theme = chartTheme();
    const datasets = withPoints.map((entry, index) => {
        const color = colorPalette[index % colorPalette.length];
        return {
            label: entry.display,
            data: entry.points,
            baseColor: color,
            borderColor: color,
            backgroundColor: color,
            borderWidth: 2,
            pointRadius: 0,
            pointHoverRadius: 4,
            tension: 0.15,
            stepped: false,
            fill: false,
        };
    });

    eloHistoryChart = new window.Chart(eloHistoryChartCanvas, {
        type: 'line',
        data: { datasets },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: { duration: theme.reducedMotion ? 0 : 400 },
            parsing: { xAxisKey: 'x', yAxisKey: 'y' },
            interaction: { mode: 'nearest', axis: 'x', intersect: false },
            plugins: {
                legend: {
                    position: 'top',
                    labels: { color: theme.text, usePointStyle: true, boxWidth: 8 },
                    // Egy modell kiemelése a jelmagyarázat fölé húzott egérrel
                    onHover: (event, item, legend) => highlightDataset(legend.chart, item.datasetIndex),
                    onLeave: (event, item, legend) => highlightDataset(legend.chart, null),
                },
                tooltip: {
                    callbacks: {
                        title: (items) => items[0]
                            ? new Date(items[0].parsed.x).toLocaleString('hu-HU', { dateStyle: 'medium', timeStyle: 'short' })
                            : '',
                        label: (ctx) => `${ctx.dataset.label}: ${ctx.parsed.y.toFixed(1)} ELO`,
                    },
                },
            },
            scales: {
                x: {
                    type: 'time',
                    time: { unit: timeUnitFor(eloHistoryRange), tooltipFormat: 'yyyy.MM.dd. HH:mm', displayFormats: { day: 'MM.dd.', week: 'MM.dd.', month: 'yyyy.MM.' } },
                    title: { display: true, text: 'Időpont', color: theme.text },
                    grid: { color: theme.grid },
                    ticks: { color: theme.muted, maxRotation: 0, autoSkipPadding: 16 },
                },
                y: {
                    title: { display: true, text: 'Online ELO', color: theme.text },
                    grid: { color: theme.grid },
                    ticks: { color: theme.muted },
                },
            },
        },
    });
}

export function refreshEloHistoryChart() {
    if (eloHistoryChart && lastSeries) renderEloHistoryChart(lastSeries);
}

export function initEloHistoryMode() {
    refreshHistoryBtn.addEventListener('click', loadEloHistoryData);
    document.querySelectorAll('input[name="elo-history-range"]').forEach((radio) => {
        radio.addEventListener('change', (event) => {
            eloHistoryRange = event.target.value;
            loadEloHistoryData();
        });
    });

    if (topNSlider && topNValue) {
        topNValue.textContent = topNSlider.value;
        topNSlider.addEventListener('input', (event) => {
            topNValue.textContent = event.target.value;
        });
        topNSlider.addEventListener('change', (event) => {
            topNCount = Number(event.target.value);
            loadEloHistoryData();
        });
    }
}
