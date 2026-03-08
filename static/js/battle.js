// filepath: d:\AI\Leaderboard-Image\static\js\battle.js
import { fetchData } from './api.js';
import { getRevealDelayMs } from './config.js';
import { isLoggedIn } from './auth.js';

// DOM elemek
const battleModeDiv = document.getElementById('battle-mode');
const battlePrompt = document.getElementById('battle-prompt');
const battlePromptPopup = document.getElementById('battle-prompt-popup');
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
        const fullPromptText = `Prompt: "${data.prompt_text}" (ID: ${data.prompt_id})`;
        battlePrompt.textContent = fullPromptText;
        battlePromptPopup.textContent = fullPromptText;
        battlePromptPopup.style.display = 'none';
        battlePrompt.classList.remove('prompt-open');
        // A modellek valódi neveit itt már nem állítjuk be, csak a szavazás után.
        battleImage1.src = data.model1.image_url;
        battleImage2.src = data.model2.image_url;
        if (isLoggedIn()) {
            disableVoting(false);
        } else {
            // Only disable vote buttons, keep tie and skip for browsing
            voteBtn1.disabled = true;
            voteBtn2.disabled = true;
            tieBtn.disabled = false;
            skipBtn.disabled = false;
            const loginMsg = document.getElementById('login-required-message');
            if (loginMsg) loginMsg.style.display = 'block';
        }
        
        // Adjust height after images are set
        // setTimeout(adjustImageHeight, 0);
    } else {
        battlePrompt.textContent = "Hiba a prompt betöltése közben.";
    }
}

async function handleVote(winnerId, loserId) {
    if (!currentBattleData || !isLoggedIn()) return;
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
        const m1 = currentBattleData.model1;
        const m2 = currentBattleData.model2;
        battleModel1Name.textContent = m1.provider ? `${m1.provider}: ${m1.name}` : m1.name;
        battleModel2Name.textContent = m2.provider ? `${m2.provider}: ${m2.name}` : m2.name;
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
            const m1t = currentBattleData.model1;
            const m2t = currentBattleData.model2;
            battleModel1Name.textContent = m1t.provider ? `${m1t.provider}: ${m1t.name}` : m1t.name;
            battleModel2Name.textContent = m2t.provider ? `${m2t.provider}: ${m2t.name}` : m2t.name;
            setTimeout(() => {
                loadBattleData();
            }, getRevealDelayMs());
        } else {
            loadBattleData();
        }
    });
    skipBtn.addEventListener('click', () => {
        if (currentBattleData) {
            const m1s = currentBattleData.model1;
            const m2s = currentBattleData.model2;
            battleModel1Name.textContent = m1s.provider ? `${m1s.provider}: ${m1s.name}` : m1s.name;
            battleModel2Name.textContent = m2s.provider ? `${m2s.provider}: ${m2s.name}` : m2s.name;
            setTimeout(() => {
                loadBattleData();
            }, getRevealDelayMs());
        } else {
            loadBattleData();
        }
    });

    // Prompt kinyitása/becsukása kattintásra
    battlePrompt.addEventListener('click', (e) => {
        e.stopPropagation();
        const isOpen = battlePromptPopup.style.display !== 'none';
        battlePromptPopup.style.display = isOpen ? 'none' : 'block';
        battlePrompt.classList.toggle('prompt-open', !isOpen);
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
        if (battleModeDiv.offsetParent === null || !currentBattleData) {
            return;
        }

        switch (event.key) {
            case '1':
                if (!voteBtn1.disabled) voteBtn1.click();
                break;
            case '2':
                if (!voteBtn2.disabled) voteBtn2.click();
                break;
            case '0':
                if (!tieBtn.disabled) tieBtn.click();
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
