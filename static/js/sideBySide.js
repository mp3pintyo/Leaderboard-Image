import { requestJson } from './api.js';
import { getModelDisplay } from './config.js';
import { preloadImages } from './imageLoading.js';
import { showToast } from './toast.js';

// DOM elemek
const sbsModeDiv = document.getElementById('side-by-side-mode');
const selects = [
    document.getElementById('sbs-model1-select'),
    document.getElementById('sbs-model2-select'),
    document.getElementById('sbs-model3-select'),
];
const sbsLoadBtn = document.getElementById('sbs-load-btn');
const sbsNextBtn = document.getElementById('sbs-next-btn');
const sbsPrompt = document.getElementById('sbs-prompt');
const sbsPromptPopup = document.getElementById('sbs-prompt-popup');
const slots = [1, 2, 3].map((index) => ({
    container: document.getElementById(index === 3 ? 'sbs-model3-container' : `sbs-model${index}-img-container`),
    name: document.getElementById(`sbs-model${index}-name`),
    image: document.getElementById(`sbs-image${index}`),
}));

// Állapot
let currentPromptId = null;
let requestSeq = 0;

// A side-by-side nézet pontosan kitölti a látható területet a fix navbar alatt
export function adjustImageHeight() {
    if (!sbsModeDiv || sbsModeDiv.offsetParent === null) return;
    if (window.matchMedia('(max-width: 767.98px)').matches) {
        sbsModeDiv.style.height = 'auto';
        return;
    }
    const topOffset = sbsModeDiv.getBoundingClientRect().top;
    const availableHeight = Math.floor(window.innerHeight - topOffset - 4);
    sbsModeDiv.style.height = `${Math.max(280, availableHeight)}px`;
}

function adjustColumnSizes(numModels) {
    const baseClasses = 'h-100 d-flex flex-column text-center px-2';
    const col = numModels === 3 ? 'col-md-4' : 'col-md-6';
    slots.forEach((slot) => { slot.container.className = `${col} ${baseClasses}`; });
    slots[2].container.hidden = numModels !== 3;
}

function selectedModels() {
    return selects.map((select) => select.value).filter(Boolean);
}

function setPromptOpen(open) {
    sbsPromptPopup.style.display = open ? 'block' : 'none';
    sbsPrompt.classList.toggle('prompt-open', open);
    sbsPrompt.setAttribute('aria-expanded', String(open));
}

/**
 * Betölt egy promptot a kiválasztott modellekkel.
 * @param {{prompt_id?: string, after?: string, previous_prompt_id?: string}} target
 */
async function loadSideBySide(target = {}) {
    const models = selectedModels();
    if (models.length < 2 || !selects[0].value || !selects[1].value) {
        showToast('Válassz ki legalább két modellt!', 'warning');
        return false;
    }
    if (new Set(models).size !== models.length) {
        showToast('Különböző modelleket válassz!', 'warning');
        return false;
    }

    const params = new URLSearchParams();
    models.forEach((model, index) => params.set(`model${index + 1}`, model));
    Object.entries(target).forEach(([key, value]) => { if (value) params.set(key, value); });

    const seq = ++requestSeq;
    sbsLoadBtn.disabled = true;
    sbsNextBtn.disabled = true;
    try {
        const data = await requestJson(`/api/side_by_side_data?${params}`);
        const entries = [data.model1, data.model2, data.model3].filter(Boolean);
        // Az új képek letöltése és dekódolása alatt a régiek látszanak (nincs villogás)
        await preloadImages(entries.map((entry) => entry.image_url)).catch((error) => {
            console.warn('Side-by-side preload failed:', error);
        });
        if (seq !== requestSeq) return true; // Időközben újabb kérés indult

        currentPromptId = data.prompt_id;
        const fullText = `Prompt: "${data.prompt_text}" (ID: ${data.prompt_id})`;
        sbsPrompt.textContent = fullText;
        sbsPromptPopup.textContent = fullText;
        setPromptOpen(false);

        adjustColumnSizes(entries.length);
        entries.forEach((entry, index) => {
            const display = entry.display || entry.name || getModelDisplay(entry.id);
            slots[index].name.textContent = display;
            slots[index].image.src = entry.image_url;
            slots[index].image.alt = `${display} képe`;
        });
        if (entries.length < 3) {
            slots[2].image.removeAttribute('src');
            slots[2].name.textContent = 'Modell 3';
        }
        return true;
    } catch (error) {
        if (seq === requestSeq) showToast(error.message, error.status === 404 ? 'warning' : 'danger');
        return false;
    } finally {
        if (seq === requestSeq) {
            sbsLoadBtn.disabled = false;
            sbsNextBtn.disabled = false;
            setTimeout(adjustImageHeight, 0);
        }
    }
}

async function handleModelChange() {
    if (!selectedModels().length) return;
    adjustColumnSizes(selects[2].value ? 3 : 2);
    if (!currentPromptId) {
        setTimeout(adjustImageHeight, 0);
        return;
    }
    // Ugyanazt a promptot próbáljuk; ha az új modellnek nincs hozzá képe, véletlen közös promptra váltunk
    const ok = await loadSideBySide({ prompt_id: currentPromptId });
    if (!ok && new Set(selectedModels()).size === selectedModels().length) {
        await loadSideBySide({ previous_prompt_id: currentPromptId });
    }
}

export function initSideBySideMode() {
    const togglePrompt = () => setPromptOpen(sbsPromptPopup.style.display === 'none');
    sbsPrompt.addEventListener('click', togglePrompt);
    sbsPrompt.addEventListener('keydown', (event) => {
        if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault();
            togglePrompt();
        }
    });

    selects.forEach((select) => select.addEventListener('change', handleModelChange));
    sbsLoadBtn.addEventListener('click', () => loadSideBySide({ previous_prompt_id: currentPromptId }));
    sbsNextBtn.addEventListener('click', () => loadSideBySide({ after: currentPromptId || '0' }));
    window.addEventListener('resize', adjustImageHeight);

    adjustColumnSizes(selects[2].value ? 3 : 2);
}
