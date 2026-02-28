import { fetchData } from './api.js';

// DOM elemek
const compareModel1Select = document.getElementById('compare-model1-select');
const compareModel2Select = document.getElementById('compare-model2-select');
const compareBtn = document.getElementById('compare-load-btn');
const compareResultDiv = document.getElementById('compare-result');

let compareChart = null; // Chart.js instance

function getTagBadgeClass(tag) {
    const map = {
        'photorealistic': 'bg-primary',
        'artistic': 'bg-info text-dark',
        'general': 'bg-secondary',
        'multimodal': 'bg-warning text-dark',
        'text-rendering': 'bg-success',
        'editing': 'bg-danger',
        'inpainting': 'bg-danger',
        'stylized': 'bg-info text-dark',
        'lightweight': 'bg-light text-dark',
        'fast': 'bg-success',
        'high-resolution': 'bg-primary',
        'commercial-safe': 'bg-dark',
        'flexible': 'bg-secondary',
    };
    return map[tag] || 'bg-secondary';
}

function getSpeedBadge(speed) {
    const map = {
        'fast': '<span class="badge bg-success">⚡ Gyors</span>',
        'medium': '<span class="badge bg-warning text-dark">⏱ Közepes</span>',
        'slow': '<span class="badge bg-danger">🐢 Lassú</span>',
    };
    return map[speed] || '<span class="badge bg-secondary">N/A</span>';
}

function renderModelCard(model, side) {
    const tags = (model.tags || []).map(t => `<span class="badge ${getTagBadgeClass(t)} me-1">${t}</span>`).join('');
    const openSourceBadge = model.open_source
        ? '<span class="badge bg-success">Open Source</span>'
        : '<span class="badge bg-warning text-dark">Zárt forrású</span>';
    const apiAvailable = model.api_available
        ? '<span class="badge bg-success">✓ Elérhető</span>'
        : '<span class="badge bg-danger">✗ Nem elérhető</span>';
    const website = model.website
        ? `<a href="${model.website}" target="_blank" rel="noopener noreferrer" class="text-decoration-none">${model.website}</a>`
        : '<span class="text-muted">N/A</span>';

    return `
        <div class="card compare-model-card h-100 ${side === 'left' ? 'border-primary' : 'border-success'}">
            <div class="card-header ${side === 'left' ? 'bg-primary' : 'bg-success'} text-white">
                <h5 class="mb-0">${model.name}</h5>
            </div>
            <div class="card-body">
                <table class="table table-sm table-borderless mb-0">
                    <tbody>
                        <tr><td class="fw-bold text-nowrap" style="width:40%">Szolgáltató</td><td>${model.provider}</td></tr>
                        <tr><td class="fw-bold">Típus</td><td>${openSourceBadge}</td></tr>
                        <tr><td class="fw-bold">Kategória</td><td><span class="badge bg-dark">${model.type || 'N/A'}</span></td></tr>
                        <tr><td class="fw-bold">Megjelenés</td><td>${model.release_date || 'N/A'}</td></tr>
                        <tr><td class="fw-bold">Max felbontás</td><td>${model.max_resolution || 'N/A'}</td></tr>
                        <tr><td class="fw-bold">Árazás</td><td>${model.pricing || 'N/A'}</td></tr>
                        <tr><td class="fw-bold">API</td><td>${apiAvailable}</td></tr>
                        <tr><td class="fw-bold">Sebesség</td><td>${getSpeedBadge(model.speed)}</td></tr>
                        <tr><td class="fw-bold">Weboldal</td><td>${website}</td></tr>
                        <tr><td class="fw-bold">Címkék</td><td>${tags || '<span class="text-muted">Nincs</span>'}</td></tr>
                    </tbody>
                </table>
            </div>
        </div>
    `;
}

function renderStatsOverview(stats) {
    const m1 = stats.model1;
    const m2 = stats.model2;
    const h2h = stats.head_to_head;

    // Head-to-head bar percentages
    let h2hBar = '';
    if (h2h.total > 0) {
        const pct1 = Math.round(h2h.model1_wins / h2h.total * 100);
        const pct2 = 100 - pct1;
        h2hBar = `
            <div class="progress" style="height: 30px;">
                <div class="progress-bar bg-primary" style="width: ${pct1}%">${m1.name}: ${h2h.model1_wins} (${pct1}%)</div>
                <div class="progress-bar bg-success" style="width: ${pct2}%">${m2.name}: ${h2h.model2_wins} (${pct2}%)</div>
            </div>
        `;
    } else {
        h2hBar = '<p class="text-muted text-center">Még nem játszottak egymás ellen</p>';
    }

    return `
        <div class="card mb-4">
            <div class="card-header bg-dark text-white"><h5 class="mb-0">📊 Összesített statisztikák</h5></div>
            <div class="card-body">
                <div class="row text-center mb-3">
                    <div class="col-md-6">
                        <div class="border rounded p-3">
                            <h6 class="text-primary">${m1.name}</h6>
                            <div class="display-6 fw-bold text-primary">${m1.elo}</div>
                            <small class="text-muted">ELO</small>
                            <div class="mt-2">
                                <span class="badge bg-primary">${m1.wins} győzelem</span>
                                <span class="badge bg-secondary">${m1.matches} meccs</span>
                                <span class="badge bg-info text-dark">${m1.win_rate}% WR</span>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-6">
                        <div class="border rounded p-3">
                            <h6 class="text-success">${m2.name}</h6>
                            <div class="display-6 fw-bold text-success">${m2.elo}</div>
                            <small class="text-muted">ELO</small>
                            <div class="mt-2">
                                <span class="badge bg-success">${m2.wins} győzelem</span>
                                <span class="badge bg-secondary">${m2.matches} meccs</span>
                                <span class="badge bg-info text-dark">${m2.win_rate}% WR</span>
                            </div>
                        </div>
                    </div>
                </div>
                <h6 class="text-center mb-2">⚔️ Egymás elleni eredmények (${h2h.total} meccs)</h6>
                ${h2hBar}
            </div>
        </div>
    `;
}

function renderRadarChart(stats, info) {
    const canvas = document.getElementById('compare-radar-chart');
    if (!canvas) return;
    
    if (compareChart) {
        compareChart.destroy();
        compareChart = null;
    }

    const m1 = stats.model1;
    const m2 = stats.model2;

    // Normalized metrics for radar (0-100 scale)
    const maxElo = Math.max(m1.elo, m2.elo, 1600);
    const minElo = Math.min(1400, m1.elo, m2.elo);
    const eloRange = maxElo - minElo || 1;

    function normalize(val, min, max) {
        if (max === min) return 50;
        return Math.round(((val - min) / (max - min)) * 100);
    }

    const labels = ['ELO Rating', 'Győzelmi arány', 'Meccsek száma', 'Győzelmek'];
    const maxMatches = Math.max(m1.matches, m2.matches, 1);
    const maxWins = Math.max(m1.wins, m2.wins, 1);

    const data1 = [
        normalize(m1.elo, minElo, maxElo),
        m1.win_rate,
        normalize(m1.matches, 0, maxMatches),
        normalize(m1.wins, 0, maxWins),
    ];

    const data2 = [
        normalize(m2.elo, minElo, maxElo),
        m2.win_rate,
        normalize(m2.matches, 0, maxMatches),
        normalize(m2.wins, 0, maxWins),
    ];

    compareChart = new Chart(canvas, {
        type: 'radar',
        data: {
            labels: labels,
            datasets: [
                {
                    label: m1.name,
                    data: data1,
                    backgroundColor: 'rgba(13, 110, 253, 0.15)',
                    borderColor: 'rgba(13, 110, 253, 1)',
                    pointBackgroundColor: 'rgba(13, 110, 253, 1)',
                    borderWidth: 2,
                },
                {
                    label: m2.name,
                    data: data2,
                    backgroundColor: 'rgba(25, 135, 84, 0.15)',
                    borderColor: 'rgba(25, 135, 84, 1)',
                    pointBackgroundColor: 'rgba(25, 135, 84, 1)',
                    borderWidth: 2,
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            scales: {
                r: {
                    beginAtZero: true,
                    max: 100,
                    ticks: { display: false },
                    pointLabels: { font: { size: 12 } }
                }
            },
            plugins: {
                legend: { position: 'top' }
            }
        }
    });
}

function renderPromptStats(stats) {
    const promptStats = stats.prompt_stats;
    if (!promptStats || promptStats.length === 0) {
        return '<p class="text-muted text-center">Nincs prompt szintű adat</p>';
    }

    const rows = promptStats.map(p => {
        const m1WinPct = p.model1.win_rate;
        const m2WinPct = p.model2.win_rate;
        const m1BarColor = m1WinPct >= m2WinPct ? 'bg-primary' : 'bg-primary bg-opacity-50';
        const m2BarColor = m2WinPct >= m1WinPct ? 'bg-success' : 'bg-success bg-opacity-50';

        return `
            <tr>
                <td class="text-nowrap"><small>${p.prompt_id}</small></td>
                <td><small class="text-truncate d-inline-block" style="max-width:200px" title="${p.prompt_text}">${p.prompt_text}</small></td>
                <td class="text-center">${p.model1.wins}/${p.model1.matches}</td>
                <td style="width:80px">
                    <div class="progress" style="height:18px">
                        <div class="progress-bar ${m1BarColor}" style="width:${m1WinPct}%"><small>${m1WinPct}%</small></div>
                    </div>
                </td>
                <td class="text-center">${p.model2.wins}/${p.model2.matches}</td>
                <td style="width:80px">
                    <div class="progress" style="height:18px">
                        <div class="progress-bar ${m2BarColor}" style="width:${m2WinPct}%"><small>${m2WinPct}%</small></div>
                    </div>
                </td>
            </tr>
        `;
    }).join('');

    return `
        <div class="card mb-4">
            <div class="card-header bg-dark text-white"><h5 class="mb-0">📝 Prompt szintű statisztikák</h5></div>
            <div class="card-body p-0">
                <div class="table-responsive">
                    <table class="table table-sm table-striped table-hover mb-0">
                        <thead class="table-light">
                            <tr>
                                <th>ID</th>
                                <th>Prompt</th>
                                <th class="text-center text-primary">Gy/M</th>
                                <th class="text-primary">WR%</th>
                                <th class="text-center text-success">Gy/M</th>
                                <th class="text-success">WR%</th>
                            </tr>
                        </thead>
                        <tbody>${rows}</tbody>
                    </table>
                </div>
            </div>
        </div>
    `;
}

function renderWinRateBarChart(stats) {
    const promptStats = stats.prompt_stats;
    if (!promptStats || promptStats.length === 0) return '';

    // Only show prompts where at least one model has matches
    const relevantPrompts = promptStats.filter(p => p.model1.matches > 0 || p.model2.matches > 0);
    if (relevantPrompts.length === 0) return '';

    return `
        <div class="card mb-4">
            <div class="card-header bg-dark text-white"><h5 class="mb-0">📈 Győzelmi arány promptonként</h5></div>
            <div class="card-body">
                <div class="chart-container" style="position: relative; height:${Math.max(300, relevantPrompts.length * 35)}px; width:100%;">
                    <canvas id="compare-bar-chart"></canvas>
                </div>
            </div>
        </div>
    `;
}

function createWinRateBarChart(stats) {
    const canvas = document.getElementById('compare-bar-chart');
    if (!canvas) return;

    const promptStats = stats.prompt_stats.filter(p => p.model1.matches > 0 || p.model2.matches > 0);
    if (promptStats.length === 0) return;

    const labels = promptStats.map(p => p.prompt_id);

    new Chart(canvas, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [
                {
                    label: stats.model1.name + ' WR%',
                    data: promptStats.map(p => p.model1.win_rate),
                    backgroundColor: 'rgba(13, 110, 253, 0.7)',
                    borderColor: 'rgba(13, 110, 253, 1)',
                    borderWidth: 1,
                },
                {
                    label: stats.model2.name + ' WR%',
                    data: promptStats.map(p => p.model2.win_rate),
                    backgroundColor: 'rgba(25, 135, 84, 0.7)',
                    borderColor: 'rgba(25, 135, 84, 1)',
                    borderWidth: 1,
                }
            ]
        },
        options: {
            indexAxis: 'y',
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                x: {
                    beginAtZero: true,
                    max: 100,
                    title: { display: true, text: 'Győzelmi arány (%)' }
                },
                y: {
                    title: { display: true, text: 'Prompt' }
                }
            },
            plugins: {
                legend: { position: 'top' },
                tooltip: {
                    callbacks: {
                        label: function(ctx) {
                            return `${ctx.dataset.label}: ${ctx.raw}%`;
                        }
                    }
                }
            }
        }
    });
}

async function loadCompareData() {
    const model1Id = compareModel1Select.value;
    const model2Id = compareModel2Select.value;

    if (model1Id === model2Id) {
        compareResultDiv.innerHTML = '<div class="alert alert-warning text-center">Kérlek válassz két különböző modellt!</div>';
        return;
    }

    compareResultDiv.innerHTML = '<div class="text-center"><div class="spinner-border" role="status"><span class="visually-hidden">Loading...</span></div></div>';

    // Fetch model info and stats in parallel
    const [infoData, statsData] = await Promise.all([
        fetchData(`/api/model_info?model1=${model1Id}&model2=${model2Id}`),
        fetchData(`/api/compare_stats?model1=${model1Id}&model2=${model2Id}`)
    ]);

    if (!infoData || !statsData) {
        compareResultDiv.innerHTML = '<div class="alert alert-danger">Hiba az adatok betöltése közben.</div>';
        return;
    }

    const html = `
        <!-- Model info cards -->
        <div class="row mb-4">
            <div class="col-md-6">${renderModelCard(infoData.model1, 'left')}</div>
            <div class="col-md-6">${renderModelCard(infoData.model2, 'right')}</div>
        </div>

        <!-- Stats overview + radar chart -->
        <div class="row mb-4">
            <div class="col-lg-7">${renderStatsOverview(statsData)}</div>
            <div class="col-lg-5">
                <div class="card h-100">
                    <div class="card-header bg-dark text-white"><h5 class="mb-0">🎯 Teljesítmény radar</h5></div>
                    <div class="card-body d-flex align-items-center justify-content-center">
                        <canvas id="compare-radar-chart"></canvas>
                    </div>
                </div>
            </div>
        </div>

        <!-- Win rate bar chart per prompt -->
        ${renderWinRateBarChart(statsData)}

        <!-- Prompt-level stats table -->
        ${renderPromptStats(statsData)}
    `;

    compareResultDiv.innerHTML = html;

    // Create charts after DOM is updated
    renderRadarChart(statsData, infoData);
    createWinRateBarChart(statsData);
}

export function initCompareMode() {
    compareBtn.addEventListener('click', loadCompareData);
    
    // Set second dropdown to a different model by default
    if (compareModel2Select.options.length > 1) {
        compareModel2Select.selectedIndex = 1;
    }
}

export { loadCompareData };
