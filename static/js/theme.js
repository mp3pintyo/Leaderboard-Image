// Világos / sötét téma kezelése (Bootstrap 5.3 data-bs-theme)
const STORAGE_KEY = 'arena-theme'; // 'light' | 'dark' | 'auto'
const media = window.matchMedia('(prefers-color-scheme: dark)');

function readPreference() {
    try {
        return localStorage.getItem(STORAGE_KEY) || 'auto';
    } catch {
        return 'auto';
    }
}

function writePreference(value) {
    try {
        localStorage.setItem(STORAGE_KEY, value);
    } catch { /* privát mód */ }
}

export function resolvedTheme(preference = readPreference()) {
    if (preference === 'light' || preference === 'dark') return preference;
    return media.matches ? 'dark' : 'light';
}

export function isDarkTheme() {
    return document.documentElement.getAttribute('data-bs-theme') === 'dark';
}

function applyTheme(preference) {
    const theme = resolvedTheme(preference);
    document.documentElement.setAttribute('data-bs-theme', theme);
    document.querySelectorAll('[data-theme-choice]').forEach((button) => {
        const active = button.dataset.themeChoice === preference;
        button.classList.toggle('active', active);
        button.setAttribute('aria-pressed', String(active));
    });
    const icon = document.getElementById('theme-toggle-icon');
    if (icon) icon.textContent = theme === 'dark' ? '☾' : '☀';
    document.dispatchEvent(new CustomEvent('themechange', { detail: { theme } }));
}

export function initTheme() {
    applyTheme(readPreference());
    document.querySelectorAll('[data-theme-choice]').forEach((button) => {
        button.addEventListener('click', () => {
            writePreference(button.dataset.themeChoice);
            applyTheme(button.dataset.themeChoice);
        });
    });
    media.addEventListener('change', () => {
        if (readPreference() === 'auto') applyTheme('auto');
    });
}

/** Diagramszínek az aktuális témához. */
export function chartTheme() {
    const dark = isDarkTheme();
    const styles = getComputedStyle(document.body);
    return {
        dark,
        text: styles.getPropertyValue('--bs-body-color').trim() || (dark ? '#dee2e6' : '#212529'),
        muted: styles.getPropertyValue('--bs-secondary-color').trim() || (dark ? '#adb5bd' : '#6c757d'),
        grid: dark ? 'rgba(255, 255, 255, 0.1)' : 'rgba(70, 82, 90, 0.12)',
        reducedMotion: window.matchMedia('(prefers-reduced-motion: reduce)').matches,
    };
}
