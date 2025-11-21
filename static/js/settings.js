// Settings mode logic

const settingsLimitSlider = document.getElementById('battle-model-limit');
const settingsLimitValue = document.getElementById('battle-model-limit-value');

// Default to max (which we can infer from the slider's max attribute if set, or just a high number)
// Since the max is set via Jinja2 in the HTML, we can trust it.
function getStoredLimit() {
    const stored = localStorage.getItem('battleModelLimit');
    if (stored) return parseInt(stored, 10);
    return parseInt(settingsLimitSlider.max, 10);
}

function updateDisplay(value) {
    const max = parseInt(settingsLimitSlider.max, 10);
    if (parseInt(value, 10) === max) {
        settingsLimitValue.textContent = "Mind (" + value + ")";
    } else {
        settingsLimitValue.textContent = value;
    }
}

export function initSettingsMode() {
    if (!settingsLimitSlider) return;

    // Initialize slider value
    const currentLimit = getStoredLimit();
    
    // Ensure the stored limit is within bounds (in case total models changed)
    const max = parseInt(settingsLimitSlider.max, 10);
    const validLimit = Math.min(Math.max(currentLimit, 2), max);
    
    settingsLimitSlider.value = validLimit;
    updateDisplay(validLimit);

    // Event listener
    settingsLimitSlider.addEventListener('input', (e) => {
        const value = e.target.value;
        updateDisplay(value);
        localStorage.setItem('battleModelLimit', value);
    });
}

export function getBattleModelLimit() {
    return getStoredLimit();
}
