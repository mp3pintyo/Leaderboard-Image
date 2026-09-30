// Authentication state management
import { APP_CONFIG } from './config.js';

const currentUser = APP_CONFIG.user || null;

export function isLoggedIn() {
    return currentUser !== null;
}

export function getCurrentUser() {
    return currentUser;
}

/** A bejelentkezés után ugyanide (az aktuális nézetre) térjünk vissza. */
export function updateLoginLinks() {
    const next = window.location.hash || '#/battle';
    document.querySelectorAll('a[data-login-provider]').forEach((link) => {
        link.href = `/auth/${link.dataset.loginPath || 'login/' + link.dataset.loginProvider}?next=${encodeURIComponent(next)}`;
    });
}

export function showLoginPrompt() {
    const loginMsg = document.getElementById('login-required-message');
    if (loginMsg) loginMsg.hidden = false;
}
