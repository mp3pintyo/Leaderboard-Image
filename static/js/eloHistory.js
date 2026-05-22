import { fetchData } from './api.js';
import { colorPalette } from './config.js';

const eloHistoryChartCanvas = document.getElementById('eloHistoryChart');
const refreshHistoryBtn = document.getElementById('refresh-history-btn');
const topNSlider = document.getElementById('top-n-slider');
const topNValue = document.getElementById('top-n-value');
let eloHistoryChart = null;
let eloHistoryRange = 'all';
let topNCount = 1; // Default to showing top 1
let legendMouseDownHandler = null;
let legendMouseUpHandler = null;

function formatDate(date, formatStr) {
    if (typeof date === 'string') date = new Date(date);
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    const hours = String(date.getHours()).padStart(2, '0');
    const minutes = String(date.getMinutes()).padStart(2, '0');
    if (formatStr === 'yyyy.MM.dd. HH:mm') return `${year}.${month}.${day}. ${hours}:${minutes}`;
    if (formatStr === 'yyyy.MM.dd.') return `${year}.${month}.${day}.`;
    if (formatStr === 'MM.dd.') return `${month}.${day}.`;
    if (formatStr === 'HH:mm') return `${hours}:${minutes}`;
    if (formatStr === 'yyyy.MM.') return `${year}.${month}.`;
    return `${year}.${month}.${day}. ${hours}:${minutes}`;
}

function getHistoryRangeDates(range) {
    const now = new Date();
    if (range === '1w') {
        const weekAgo = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
        return {from: weekAgo, to: now};
    }
    if (range === '2w') {
        const twoWeeksAgo = new Date(now.getTime() - 14 * 24 * 60 * 60 * 1000);
        return {from: twoWeeksAgo, to: now};
    }
    return null; // Teljes időtartam
}

export async function loadEloHistoryData() {
    refreshHistoryBtn.disabled = true;
    const rawData = await fetchData('/api/elo_history_with_current_elo'); // Assuming an endpoint that also returns current ELO for sorting
    if (!rawData || !rawData.history) {
        console.error('Hiba az ELO előzmények betöltése közben vagy hiányos adatok.');
        if (eloHistoryChart) eloHistoryChart.destroy();
        const ctx = eloHistoryChartCanvas.getContext('2d');
        ctx.clearRect(0, 0, eloHistoryChartCanvas.width, eloHistoryChartCanvas.height);
        ctx.textAlign = 'center';
        ctx.fillText('Hiba a grafikon adatainak betöltése közben.', eloHistoryChartCanvas.width/2, eloHistoryChartCanvas.height/2);
        refreshHistoryBtn.disabled = false;
        return;
    }

    const data = rawData.history;
    const currentElos = rawData.current_elos; // { modelName: elo, ... }

    let filteredDataByDate = data;
    if (data && eloHistoryRange !== 'all') {
        const range = getHistoryRangeDates(eloHistoryRange);
        if (range) {
            filteredDataByDate = {};
            for (const model in data) {
                filteredDataByDate[model] = data[model].filter(point => {
                    const t = new Date(point.x);
                    return t >= range.from && t <= range.to;
                });
            }
        }
    }

    // Filter by Top N based on current ELO scores
    const sortedModelsByElo = Object.entries(currentElos)
        .sort(([,a],[,b]) => b - a) // Sort by ELO descending
        .map(([modelName]) => modelName);

    const topNModelsToShow = sortedModelsByElo.slice(0, topNCount);

    const finalFilteredData = {};
    for (const model of topNModelsToShow) {
        if (filteredDataByDate[model]) {
            finalFilteredData[model] = filteredDataByDate[model];
        }
    }

    if (Object.keys(finalFilteredData).length > 0) {
        renderEloHistoryChart(finalFilteredData, Object.keys(data).length); // Pass total model count for slider max
    } else {
        console.error('Nincs adat a megadott szűrőkkel.');
        if (eloHistoryChart) eloHistoryChart.destroy();
        const ctx = eloHistoryChartCanvas.getContext('2d');
        ctx.clearRect(0, 0, eloHistoryChartCanvas.width, eloHistoryChartCanvas.height);
        ctx.textAlign = 'center';
        ctx.fillText('Nincs adat a megadott szűrőkkel.', eloHistoryChartCanvas.width/2, eloHistoryChartCanvas.height/2);
    }
    refreshHistoryBtn.disabled = false;
}

function hexToRgba(hex, alpha) {
    hex = hex.replace('#', '');
    if (hex.length === 3) hex = hex.split('').map(c => c + c).join('');
    const r = parseInt(hex.substring(0, 2), 16);
    const g = parseInt(hex.substring(2, 4), 16);
    const b = parseInt(hex.substring(4, 6), 16);
    return `rgba(${r},${g},${b},${alpha})`;
}

function renderEloHistoryChart(apiData, totalModelCount) {
    if (eloHistoryChart) eloHistoryChart.destroy();
    if (legendMouseDownHandler) {
        eloHistoryChartCanvas.removeEventListener('mousedown', legendMouseDownHandler);
        legendMouseDownHandler = null;
    }
    if (legendMouseUpHandler) {
        eloHistoryChartCanvas.removeEventListener('mouseup', legendMouseUpHandler);
        legendMouseUpHandler = null;
    }

    // Update slider max value and current display
    if (topNSlider && totalModelCount > 0) {
        topNSlider.max = totalModelCount;
        // Ensure current slider value is not out of bounds if totalModelCount changed
        if (parseInt(topNSlider.value) > totalModelCount) {
            topNSlider.value = totalModelCount;
        }
        if (topNValue) {
            topNValue.textContent = topNSlider.value;
        }
        topNCount = parseInt(topNSlider.value);
    } else if (topNSlider) {
        topNSlider.max = 1; // Default if no models
        topNSlider.value = 1;
        if (topNValue) {
            topNValue.textContent = '1';
        }
    }

    // 1. Collect all unique timestamps and sort them
    const allTimestamps = new Set();
    for (const model in apiData) {
        apiData[model].forEach(point => allTimestamps.add(new Date(point.x).getTime()));
    }
    const sortedTimestamps = Array.from(allTimestamps).sort((a, b) => a - b);

    // 2. Create labels for the category axis
    const labels = sortedTimestamps.map(ts => formatDate(new Date(ts), 'yyyy.MM.dd. HH:mm'));
    const timestampToIndex = new Map(sortedTimestamps.map((ts, index) => [ts, index]));

    // 3. Transform datasets for the category axis
    const datasets = [];
    let colorIndex = 0;
    for (const model in apiData) {
        const modelData = apiData[model];
        const categoryData = new Array(sortedTimestamps.length).fill(null);

        modelData.forEach(point => {
            const timestamp = new Date(point.x).getTime();
            const index = timestampToIndex.get(timestamp);
            if (index !== undefined) {
                categoryData[index] = point.y;
            }
        });

        // Optional: Fill nulls with the previous non-null value to make lines continuous
        // Remove this loop if you want gaps in lines when a model misses a timestamp
        let lastValue = null;
        for (let i = 0; i < categoryData.length; i++) {
            if (categoryData[i] !== null) {
                lastValue = categoryData[i];
            } else if (lastValue !== null) {
                 // Use previous value if current is null, remove if gaps are desired
                // categoryData[i] = lastValue; // Uncomment to fill gaps
            }
        }


        datasets.push({
            label: model,
            data: categoryData, // Use the transformed data
            borderColor: colorPalette[colorIndex % colorPalette.length],
            backgroundColor: colorPalette[colorIndex % colorPalette.length] + '33', // Optional: for area fill if needed
            tension: 0.1,
            fill: false,
            spanGaps: true // Connect points across null values
        });
        colorIndex++;
    }

    // 4. Render chart with category scale
    const ctx = eloHistoryChartCanvas.getContext('2d');
    eloHistoryChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels, // Use generated labels
            datasets: datasets
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                title: {
                    display: true,
                    text: 'Modellek ELO Pontszámának Változása (Sűrített Időskála)' // Updated title
                },
                legend: {
                    position: 'top'
                },
                tooltip: {
                    mode: 'index',
                    intersect: false,
                    callbacks: {
                        // Display ELO, use label (formatted date) for the title
                        label: ctx => `${ctx.dataset.label}: ${ctx.parsed.y !== null ? ctx.parsed.y.toFixed(1) : 'N/A'} ELO`,
                        title: ctx => ctx[0]?.label || '' // Tooltip title is the category label
                    }
                }
            },
            scales: {
                x: {
                    // Use 'category' scale instead of 'time'
                    type: 'category',
                    title: {
                        display: true,
                        text: 'Időpont (csak frissítésekkel)'
                    }
                    // Removed time-specific formatting
                },
                y: {
                    title: {
                        display: true,
                        text: 'ELO Pontszám'
                    },
                    beginAtZero: false
                }
            },
            interaction: {
                mode: 'nearest',
                axis: 'x',
                intersect: false
            }
        }
    });

    // store original colors for restore
    eloHistoryChart._originalBorderColors = eloHistoryChart.data.datasets.map(ds => ds.borderColor);
    eloHistoryChart._originalBackgroundColors = eloHistoryChart.data.datasets.map(ds => ds.backgroundColor);

    // fade other datasets on legend mousedown
    legendMouseDownHandler = event => {
        const rect = eloHistoryChartCanvas.getBoundingClientRect();
        const x = event.clientX - rect.left;
        const y = event.clientY - rect.top;
        eloHistoryChart.legend.legendHitBoxes.forEach((box, idx) => {
            if (x >= box.left && x <= box.left + box.width && y >= box.top && y <= box.top + box.height) {
                eloHistoryChart.data.datasets.forEach((ds, j) => {
                    if (j !== idx) {
                        ds.borderColor = hexToRgba(eloHistoryChart._originalBorderColors[j], 0.1);
                        ds.backgroundColor = hexToRgba(eloHistoryChart._originalBorderColors[j], 0.1);
                    } else {
                        ds.borderColor = eloHistoryChart._originalBorderColors[j];
                        ds.backgroundColor = eloHistoryChart._originalBackgroundColors[j];
                    }
                });
                eloHistoryChart.update();
            }
        });
    };
    eloHistoryChartCanvas.addEventListener('mousedown', legendMouseDownHandler);

    // restore full opacity on mouseup
    legendMouseUpHandler = () => {
        eloHistoryChart.data.datasets.forEach((ds, i) => {
            ds.borderColor = eloHistoryChart._originalBorderColors[i];
            ds.backgroundColor = eloHistoryChart._originalBackgroundColors[i];
        });
        eloHistoryChart.update();
    };
    eloHistoryChartCanvas.addEventListener('mouseup', legendMouseUpHandler);
}

export function initEloHistoryMode() {
    refreshHistoryBtn.addEventListener('click', loadEloHistoryData);
    document.querySelectorAll('input[name="elo-history-range"]').forEach(radio => {
        radio.addEventListener('change', e => {
            eloHistoryRange = e.target.value;
            loadEloHistoryData();
        });
    });

    if (topNSlider && topNValue) {
        topNSlider.addEventListener('input', (event) => {
            topNValue.textContent = event.target.value;
        });
        topNSlider.addEventListener('change', (event) => {
            topNCount = parseInt(event.target.value);
            loadEloHistoryData();
        });
        // Initialize slider display value
        topNValue.textContent = topNSlider.value;
        topNCount = parseInt(topNSlider.value);
    }
}
