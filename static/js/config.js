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

export const colorPalette = [
    '#0d6efd', '#6f42c1', '#d63384', '#fd7e14', '#ffc107',
    '#198754', '#20c997', '#0dcaf0', '#6c757d', '#adb5bd'
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
