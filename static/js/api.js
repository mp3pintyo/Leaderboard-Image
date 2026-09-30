// API hívások és közös függvények
import { showToast } from './toast.js';
import { showLoginPrompt } from './auth.js';

// Vékony, fix pozíciójú betöltésjelző: nem tolja el a tartalmat
const loadingIndicator = document.getElementById('loading-indicator');
let pendingRequests = 0;

function beginLoading() {
    pendingRequests += 1;
    loadingIndicator?.classList.add('active');
}

function endLoading() {
    pendingRequests = Math.max(0, pendingRequests - 1);
    if (pendingRequests === 0) loadingIndicator?.classList.remove('active');
}

export class ApiError extends Error {
    constructor(message, status, code = null) {
        super(message);
        this.name = 'ApiError';
        this.status = status;
        this.code = code;
    }
}

async function parseErrorResponse(response) {
    const contentType = response.headers.get('content-type') || '';
    if (contentType.includes('application/json')) {
        const errorData = await response.json().catch(() => null);
        if (errorData?.error) return { message: errorData.error, code: errorData.code || null };
    }
    return { message: `Szerverhiba (HTTP ${response.status}).`, code: null };
}

/**
 * JSON kérés. Hiba esetén ApiError-t dob (status + code mezővel).
 * A `json` opció JSON törzset küld; nem-GET kérésekhez automatikusan CSRF tokent csatol.
 */
export async function requestJson(url, options = {}) {
    const { json, ...requestOptions } = options;
    const method = String(requestOptions.method || 'GET').toUpperCase();
    const headers = new Headers(requestOptions.headers || {});
    const csrfToken = window.APP_CONFIG?.csrf_token;

    if (json !== undefined) {
        headers.set('Content-Type', 'application/json');
        requestOptions.body = JSON.stringify(json);
    }
    if (!['GET', 'HEAD', 'OPTIONS'].includes(method) && csrfToken && !headers.has('X-CSRF-Token')) {
        headers.set('X-CSRF-Token', csrfToken);
    }

    beginLoading();
    try {
        const response = await fetch(url, { ...requestOptions, method, headers });
        if (!response.ok) {
            const { message, code } = await parseErrorResponse(response);
            throw new ApiError(message, response.status, code);
        }
        return await response.json();
    } catch (error) {
        if (error instanceof ApiError || error.name === 'AbortError') throw error;
        throw new ApiError('Hálózati hiba. Ellenőrizd az internetkapcsolatot.', 0, 'network');
    } finally {
        endLoading();
    }
}

/**
 * Kényelmi változat: hiba esetén értesítést mutat és null-t ad vissza.
 * `silent: true` esetén nem mutat értesítést.
 */
export async function fetchData(url, options = {}) {
    const { silent = false, ...rest } = options;
    try {
        return await requestJson(url, rest);
    } catch (error) {
        if (error.name === 'AbortError') return null;
        console.error('Fetch error:', error);
        if (error.status === 401) {
            showLoginPrompt();
        } else if (!silent) {
            showToast(error.message, 'danger');
        }
        return null;
    }
}
