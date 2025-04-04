document.addEventListener('DOMContentLoaded', function() {
    const modes = ['battle', 'side-by-side', 'leaderboard', 'elo-history']; // Add elo-history mode
    const navLinks = document.querySelectorAll('.navbar-nav .nav-link');
    const loadingIndicator = document.getElementById('loading-indicator');

    // --- State Variables ---
    let currentBattleData = null;
    let currentSbsModel1 = '';
    let currentSbsModel2 = '';

    // --- DOM Elements ---
    // Battle Mode
    const battleModeDiv = document.getElementById('battle-mode');
    const battlePrompt = document.getElementById('battle-prompt');
    const battleModel1Name = document.getElementById('battle-model1-name');
    const battleImage1 = document.getElementById('battle-image1');
    const voteBtn1 = document.getElementById('vote-btn1');
    const battleModel2Name = document.getElementById('battle-model2-name');
    const battleImage2 = document.getElementById('battle-image2');
    const voteBtn2 = document.getElementById('vote-btn2');
    const tieBtn = document.getElementById('tie-btn');
    const skipBtn = document.getElementById('skip-btn');

    // Side-by-Side Mode
    const sbsModeDiv = document.getElementById('side-by-side-mode');
    const sbsModel1Select = document.getElementById('sbs-model1-select');
    const sbsModel2Select = document.getElementById('sbs-model2-select');
    const sbsLoadBtn = document.getElementById('sbs-load-btn');
    const sbsPrompt = document.getElementById('sbs-prompt');
    const sbsModel1Name = document.getElementById('sbs-model1-name');
    const sbsImage1 = document.getElementById('sbs-image1');
    const sbsModel2Name = document.getElementById('sbs-model2-name');
    const sbsImage2 = document.getElementById('sbs-image2');

    // Leaderboard Mode
    const leaderboardModeDiv = document.getElementById('leaderboard-mode');
    const leaderboardTableBody = document.getElementById('leaderboard-table-body');
    const refreshLeaderboardBtn = document.getElementById('refresh-leaderboard-btn');

    // ELO History Mode Elements
    const eloHistoryModeDiv = document.getElementById('elo-history-mode');
    const eloHistoryChartCanvas = document.getElementById('eloHistoryChart');
    const refreshHistoryBtn = document.getElementById('refresh-history-btn');
    let eloHistoryChart = null; // Variable to hold the chart instance

    // --- Utility Functions ---
    function showLoading() {
        loadingIndicator.style.display = 'block';
    }

    function hideLoading() {
        loadingIndicator.style.display = 'none';
    }

    function showMode(modeToShow) {
        modes.forEach(mode => {
            const element = document.getElementById(`${mode}-mode`);
            if (element) {
                element.style.display = mode === modeToShow ? 'block' : 'none';
            }
        });
        // Nav link active state
        navLinks.forEach(link => {
            if (link.dataset.mode === modeToShow) {
                link.classList.add('active');
            } else {
                link.classList.remove('active');
            }
        });
    }

    // --- API Call Functions ---
    async function fetchData(url, options = {}) {
        showLoading();
        try {
            const response = await fetch(url, options);
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || `HTTP error! status: ${response.status}`);
            }
            return await response.json();
        } catch (error) {
            console.error("Fetch error:", error);
            alert(`Hiba történt az adatok lekérése közben: ${error.message}`);
            return null; // Vagy dobhatnánk tovább a hibát
        } finally {
            hideLoading();
        }
    }

    // Reset style function to remove highlighting from model names
    function resetModelNameStyles() {
        battleModel1Name.classList.remove('text-success');
        battleModel2Name.classList.remove('text-success');
        battleModel1Name.style.fontWeight = 'normal';
        battleModel2Name.style.fontWeight = 'normal';
    }

    // Battle Mode Logic
    async function loadBattleData() {
        // Reset images while loading
        battleImage1.src = "";
        battleImage2.src = "";
        battlePrompt.textContent = "Új prompt betöltése...";
        
        // Reset model name colors when loading new data
        resetModelNameStyles();
        
        // Alapértelmezetten elrejtjük a modell neveket, szavazás előtt
        battleModel1Name.textContent = "Modell A";
        battleModel2Name.textContent = "Modell B";
        
        disableVoting(true); // Disable buttons while loading
        const data = await fetchData('/api/battle_data');
        if (data) {
            currentBattleData = data;
            battlePrompt.textContent = `Prompt: "${data.prompt_text}" (ID: ${data.prompt_id})`;
            
            // Csak akkor jelenítjük meg a modell neveket, ha a reveal_models igaz
            // Egyébként marad "Modell A" és "Modell B"
            if (data.reveal_models) {
                battleModel1Name.textContent = data.model1.key;
                battleModel2Name.textContent = data.model2.key;
            }
            
            battleImage1.src = data.model1.image_url;
            battleImage2.src = data.model2.image_url;
            disableVoting(false); // Enable buttons after loading
        } else {
             battlePrompt.textContent = "Hiba a prompt betöltése közben.";
             // Maybe add a retry button or message
        }
    }

    function disableVoting(disabled) {
        voteBtn1.disabled = disabled;
        voteBtn2.disabled = disabled;
        tieBtn.disabled = disabled;
        skipBtn.disabled = disabled;
    }

    async function handleVote(winner, loser) {
        if (!currentBattleData) return;
        disableVoting(true); // Prevent double voting
        const voteData = {
            prompt_id: currentBattleData.prompt_id,
            winner: winner,
            loser: loser
        };
        const result = await fetchData('/api/vote', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(voteData)
        });
        if (result && result.success) {
            console.log("Vote successful:", result.message);
            
            // Szavazás után megjelenítjük a modellek neveit, mielőtt új csatát töltenénk
            battleModel1Name.textContent = currentBattleData.model1.key;
            battleModel2Name.textContent = currentBattleData.model2.key;
            
            // Győztes modell nevének kiemelése zöld színnel
            if (winner === currentBattleData.model1.key) {
                battleModel1Name.classList.add('text-success');
                battleModel1Name.style.fontWeight = 'bold';
            } else if (winner === currentBattleData.model2.key) {
                battleModel2Name.classList.add('text-success');
                battleModel2Name.style.fontWeight = 'bold';
            }
            
            // A szavazás utáni várakozási időt a konfigurációból olvassuk
            setTimeout(() => {
                loadBattleData(); // Load next battle automatically
            }, REVEAL_DELAY_MS); // Konfigurálható késleltetés
        } else {
            alert("Hiba történt a szavazás rögzítésekor.");
            disableVoting(false); // Re-enable buttons on error
        }
    }

    voteBtn1.addEventListener('click', () => {
        if (currentBattleData) {
             handleVote(currentBattleData.model1.key, currentBattleData.model2.key);
        }
    });

    voteBtn2.addEventListener('click', () => {
         if (currentBattleData) {
            handleVote(currentBattleData.model2.key, currentBattleData.model1.key);
         }
    });

    // Döntetlen/Kihagyás esetén nem küldünk szavazatot, csak újat töltünk
    // De előtte megmutatjuk a modellek neveit
    tieBtn.addEventListener('click', () => {
        console.log("Tie / Neither chosen, skipping vote.");
        
        // Megmutatjuk a modellek neveit döntetlen esetén is
        if (currentBattleData) {
            battleModel1Name.textContent = currentBattleData.model1.key;
            battleModel2Name.textContent = currentBattleData.model2.key;
            
            // A szavazás utáni várakozási időt a konfigurációból olvassuk
            setTimeout(() => {
                loadBattleData();
            }, REVEAL_DELAY_MS); // Konfigurálható késleltetés
        } else {
            loadBattleData();
        }
    });

    skipBtn.addEventListener('click', () => {
        console.log("Skipping prompt.");
        
        // Megmutatjuk a modellek neveit kihagyás esetén is
        if (currentBattleData) {
            battleModel1Name.textContent = currentBattleData.model1.key;
            battleModel2Name.textContent = currentBattleData.model2.key;
            
            // A szavazás utáni várakozási időt a konfigurációból olvassuk
            setTimeout(() => {
                loadBattleData();
            }, REVEAL_DELAY_MS); // Konfigurálható késleltetés
        } else {
            loadBattleData();
        }
    });


    // Side-by-Side Mode Logic
    function updateSbsSelection() {
        currentSbsModel1 = sbsModel1Select.value;
        currentSbsModel2 = sbsModel2Select.value;
    }

    async function loadSideBySideData() {
        if (!currentSbsModel1 || !currentSbsModel2) {
            alert("Kérlek válassz ki mindkét modellt!");
            return;
        }
        if (currentSbsModel1 === currentSbsModel2) {
            alert("Kérlek válassz két különböző modellt!");
            return;
        }

        // Reset images while loading
        sbsImage1.src = "";
        sbsImage2.src = "";
        sbsPrompt.textContent = "Prompt betöltése...";
        sbsModel1Name.textContent = currentSbsModel1;
        sbsModel2Name.textContent = currentSbsModel2;
        sbsLoadBtn.disabled = true;

        const data = await fetchData(`/api/side_by_side_data?model1=${currentSbsModel1}&model2=${currentSbsModel2}`);
        if (data) {
            sbsPrompt.textContent = `Prompt: "${data.prompt_text}" (ID: ${data.prompt_id})`;
            sbsImage1.src = data.model1.image_url;
            sbsImage2.src = data.model2.image_url;
        } else {
             sbsPrompt.textContent = "Hiba a prompt betöltése közben.";
        }
        sbsLoadBtn.disabled = false;
    }

    sbsModel1Select.addEventListener('change', updateSbsSelection);
    sbsModel2Select.addEventListener('change', updateSbsSelection);
    sbsLoadBtn.addEventListener('click', loadSideBySideData);


    // Leaderboard Mode Logic
    async function loadLeaderboardData() {
        leaderboardTableBody.innerHTML = '<tr><td colspan="6" class="text-center">Leaderboard betöltése...</td></tr>';
        refreshLeaderboardBtn.disabled = true;

        const data = await fetchData('/api/leaderboard');
        if (data) {
            leaderboardTableBody.innerHTML = ''; // Clear loading message
            if (data.length === 0) {
                 leaderboardTableBody.innerHTML = '<tr><td colspan="6" class="text-center">Még nincsenek szavazatok.</td></tr>';
            } else {
                data.forEach((row, index) => {
                    const tr = document.createElement('tr');
                    tr.innerHTML = `
                        <td>${index + 1}</td>
                        <td>${row.model}</td>
                        <td><strong>${row.elo}</strong></td>
                        <td>${row.wins}</td>
                        <td>${row.matches}</td>
                        <td>${row.win_rate}%</td>
                    `;
                    leaderboardTableBody.appendChild(tr);
                });
            }
        } else {
            leaderboardTableBody.innerHTML = '<tr><td colspan="6" class="text-center">Hiba a leaderboard betöltése közben.</td></tr>';
        }
        refreshLeaderboardBtn.disabled = false;
    }

     refreshLeaderboardBtn.addEventListener('click', loadLeaderboardData);


    // ELO History Mode Logic
    async function loadEloHistoryData() {
        showLoading();
        refreshHistoryBtn.disabled = true;
        const data = await fetchData('/api/elo_history');
        hideLoading(); // Hide loading indicator after fetch
        
        if (data) {
            renderEloHistoryChart(data);
        } else {
            // Handle error - maybe display a message on the canvas or an alert
            console.error("Hiba az ELO előzmények betöltése közben.");
            if (eloHistoryChart) {
                eloHistoryChart.destroy(); // Clear previous chart if error
            }
            const ctx = eloHistoryChartCanvas.getContext('2d');
            ctx.clearRect(0, 0, eloHistoryChartCanvas.width, eloHistoryChartCanvas.height);
            ctx.textAlign = 'center';
            ctx.fillText('Hiba a grafikon adatainak betöltése közben.', eloHistoryChartCanvas.width / 2, eloHistoryChartCanvas.height / 2);
        }
        refreshHistoryBtn.disabled = false;
    }

    function renderEloHistoryChart(apiData) {
        if (eloHistoryChart) {
            eloHistoryChart.destroy(); // Destroy previous chart instance if exists
        }
        
        const datasets = [];
        const modelColors = {}; // Store colors for consistency
        const colorPalette = [
            '#0d6efd', '#6f42c1', '#d63384', '#fd7e14', '#ffc107', 
            '#198754', '#20c997', '#0dcaf0', '#6c757d', '#adb5bd'
        ];
        let colorIndex = 0;

        for (const model in apiData) {
            if (!modelColors[model]) {
                modelColors[model] = colorPalette[colorIndex % colorPalette.length];
                colorIndex++;
            }
            
            datasets.push({
                label: model,
                data: apiData[model],
                borderColor: modelColors[model],
                backgroundColor: modelColors[model] + '33', // Semi-transparent fill
                tension: 0.1, // Smooth lines slightly
                fill: false, // Don't fill area under the line by default
                parsing: {
                    xAxisKey: 'x', // Tell Chart.js which property is for the x-axis
                    yAxisKey: 'y'  // Tell Chart.js which property is for the y-axis
                }
            });
        }

        const ctx = eloHistoryChartCanvas.getContext('2d');
        eloHistoryChart = new Chart(ctx, {
            type: 'line',
            data: { datasets },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    title: {
                        display: true,
                        text: 'Modellek ELO Pontszámának Változása az Időben'
                    },
                    legend: {
                        position: 'top',
                    },
                    tooltip: {
                        mode: 'index',
                        intersect: false,
                    }
                },
                scales: {
                    x: {
                        type: 'time',
                        time: {
                            unit: 'day', // Adjust based on data density (e.g., 'hour', 'week')
                            tooltipFormat: 'yyyy. MM. dd. HH:mm', // Format for tooltips
                            displayFormats: {
                                day: 'yyyy. MM. dd.' // Format for axis labels
                            }
                        },
                        title: {
                            display: true,
                            text: 'Dátum'
                        }
                    },
                    y: {
                        title: {
                            display: true,
                            text: 'ELO Pontszám'
                        },
                        beginAtZero: false // ELO can be high, no need to start at 0
                    }
                },
                interaction: {
                    mode: 'nearest',
                    axis: 'x',
                    intersect: false
                }
            }
        });
    }

    refreshHistoryBtn.addEventListener('click', loadEloHistoryData);

    // --- Navigation ---
    navLinks.forEach(link => {
        link.addEventListener('click', (e) => {
            e.preventDefault();
            const mode = link.dataset.mode;
            showMode(mode);

            // Load initial data for the selected mode
            if (mode === 'battle') {
                if (!currentBattleData) loadBattleData();
            } else if (mode === 'side-by-side') {
                updateSbsSelection();
                if(sbsImage1.src || sbsImage2.src) {
                   sbsPrompt.textContent = "Válassz modelleket és kattints a Betöltés gombra...";
                   sbsImage1.src = "";
                   sbsImage2.src = "";
                }
            } else if (mode === 'leaderboard') {
                loadLeaderboardData();
            } else if (mode === 'elo-history') { // Load data when switching to history mode
                loadEloHistoryData();
            }
        });
    });

    // --- Initial Load ---
    showMode('battle'); // Start in Battle mode
    loadBattleData(); // Load the first battle
});