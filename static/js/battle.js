// filepath: d:\AI\Leaderboard-Image\static\js\battle.js
import { fetchData } from './api.js';
import { getRevealDelayMs } from './config.js';

// DOM elemek
const battleModeDiv = document.getElementById('battle-mode');
const battlePrompt = document.getElementById('battle-prompt');
const battleModel1Name = document.getElementById('battle-model1-name');
const battleImage1 = document.getElementById('battle-image1');
const battleImage1Wrapper = document.getElementById('battle-image1-wrapper');
const voteBtn1 = document.getElementById('vote-btn1');
const battleModel2Name = document.getElementById('battle-model2-name');
const battleImage2 = document.getElementById('battle-image2');
const battleImage2Wrapper = document.getElementById('battle-image2-wrapper');
const voteBtn2 = document.getElementById('vote-btn2');
const tieBtn = document.getElementById('tie-btn');
const skipBtn = document.getElementById('skip-btn');

// Állapot
let currentBattleData = null;

// Segédfüggvények
function resetModelNameStyles() {
    battleModel1Name.classList.remove('text-success');
    battleModel2Name.classList.remove('text-success');
    battleModel1Name.style.fontWeight = 'normal';
    battleModel2Name.style.fontWeight = 'normal';
}
function disableVoting(disabled) {
    voteBtn1.disabled = disabled;
    voteBtn2.disabled = disabled;
    tieBtn.disabled = disabled;
    skipBtn.disabled = disabled;
}

// Helper function to dynamically adjust image max-height
function adjustImageHeight() {
    // No-op: Layout is now handled by CSS Flexbox
    return;
}

// Add resize listener
// window.addEventListener('resize', adjustImageHeight);

export async function loadBattleData() {
    battleImage1.src = "";
    battleImage2.src = "";
    battlePrompt.textContent = "Új prompt betöltése...";
    resetModelNameStyles();
    battleModel1Name.textContent = "Modell A";
    battleModel2Name.textContent = "Modell B";
    disableVoting(true);
    const data = await fetchData('/api/battle_data');
    if (data) {
        currentBattleData = data;
        battlePrompt.textContent = `Prompt: "${data.prompt_text}" (ID: ${data.prompt_id})`;
        // A modellek valódi neveit itt már nem állítjuk be, csak a szavazás után.
        battleImage1.src = data.model1.image_url;
        battleImage2.src = data.model2.image_url;
        disableVoting(false);
        
        // Adjust height after images are set
        // setTimeout(adjustImageHeight, 0);
    } else {
        battlePrompt.textContent = "Hiba a prompt betöltése közben.";
    }
}

async function handleVote(winnerId, loserId) {
    if (!currentBattleData) return;
    disableVoting(true);
    const voteData = {
        prompt_id: currentBattleData.prompt_id,
        winner: winnerId,
        loser: loserId
    };
    const result = await fetchData('/api/vote', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(voteData)
    });
    if (result && result.success) {
        battleModel1Name.textContent = currentBattleData.model1.name;
        battleModel2Name.textContent = currentBattleData.model2.name;
        if (winnerId === currentBattleData.model1.id) {
            battleModel1Name.classList.add('text-success');
            battleModel1Name.style.fontWeight = 'bold';
        } else if (winnerId === currentBattleData.model2.id) {
            battleModel2Name.classList.add('text-success');
            battleModel2Name.style.fontWeight = 'bold';
        }
        setTimeout(() => {
            loadBattleData();
        }, getRevealDelayMs());
    } else {
        disableVoting(false);
    }
}

export function initBattleMode() {
    voteBtn1.addEventListener('click', () => {
        if (currentBattleData) {
            handleVote(currentBattleData.model1.id, currentBattleData.model2.id);
        }
    });
    voteBtn2.addEventListener('click', () => {
        if (currentBattleData) {
            handleVote(currentBattleData.model2.id, currentBattleData.model1.id);
        }
    });
    tieBtn.addEventListener('click', () => {
        if (currentBattleData) {
            battleModel1Name.textContent = currentBattleData.model1.name;
            battleModel2Name.textContent = currentBattleData.model2.name;
            setTimeout(() => {
                loadBattleData();
            }, getRevealDelayMs());
        } else {
            loadBattleData();
        }
    });
    skipBtn.addEventListener('click', () => {
        if (currentBattleData) {
            battleModel1Name.textContent = currentBattleData.model1.name;
            battleModel2Name.textContent = currentBattleData.model2.name;
            setTimeout(() => {
                loadBattleData();
            }, getRevealDelayMs());
        } else {
            loadBattleData();
        }
    });

    document.addEventListener('keydown', (event) => {
        // Prevent shortcuts if user is typing in an input, textarea, or contentEditable element
        const targetTagName = event.target.tagName;
        if (targetTagName === 'INPUT' || targetTagName === 'TEXTAREA' || event.target.isContentEditable) {
            return;
        }

        // Check if the battle mode UI is currently visible and active
        // and if voting is currently allowed (buttons are not disabled)
        // battleModeDiv.offsetParent will be null if the element or its parents are display:none
        if (battleModeDiv.offsetParent === null || !currentBattleData || voteBtn1.disabled) {
            return;
        }

        switch (event.key) {
            case '1':
                voteBtn1.click();
                break;
            case '2':
                voteBtn2.click();
                break;
            case '0':
                tieBtn.click();
                break;
        }
    });

    // Add resize listener
    window.addEventListener('resize', adjustImageHeight);
    
    // Initial adjustment
    // adjustImageHeight();
}

// Ensure adjustImageHeight is called when the module loads (if DOM is ready)
if (document.readyState === 'loading') {
    // document.addEventListener('DOMContentLoaded', adjustImageHeight);
} else {
    // adjustImageHeight();
}
