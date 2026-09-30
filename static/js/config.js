// Konfigurációs beállítások és konstansok

// A szerver által renderelt beállítások (templates/index.html, #app-config JSON blokk)
const configElement = document.getElementById('app-config');
export const APP_CONFIG = (() => {
    try {
        return configElement ? JSON.parse(configElement.textContent) : {};
    } catch (error) {
        console.error('Invalid app config', error);
        return {};
    }
})();
window.APP_CONFIG = APP_CONFIG;

// 20 jól megkülönböztethető szín (világos és sötét háttéren is olvasható)
export const colorPalette = [
    '#4e79a7', '#f28e2b', '#e15759', '#76b7b2', '#59a14f',
    '#edc948', '#b07aa1', '#ff9da7', '#9c755f', '#bab0ac',
    '#1f77b4', '#d62728', '#2ca02c', '#9467bd', '#8c564b',
    '#e377c2', '#17becf', '#bcbd22', '#ff7f0e', '#7f7f7f'
];

// Alapértelmezett késleltetési idő, amire visszaesik, ha nem lenne máshogy beállítva
export const DEFAULT_REVEAL_DELAY_MS = 1500;

export function getRevealDelayMs() {
    const value = Number(APP_CONFIG.reveal_delay_ms);
    return Number.isFinite(value) && value >= 0 ? value : DEFAULT_REVEAL_DELAY_MS;
}

export function getModels() {
    return Array.isArray(APP_CONFIG.models) ? APP_CONFIG.models : [];
}

export function getModelDisplay(modelId) {
    const model = getModels().find((m) => m.id === modelId);
    return model ? model.display : modelId;
}
