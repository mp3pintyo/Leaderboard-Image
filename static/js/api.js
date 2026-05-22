// API hívások és közös függvények
export const loadingIndicator = document.getElementById('loading-indicator');

export function showLoading() {
    loadingIndicator.style.display = 'block';
}

export function hideLoading() {
    loadingIndicator.style.display = 'none';
}

async function parseErrorResponse(response) {
    const contentType = response.headers.get('content-type') || '';

    if (contentType.includes('application/json')) {
        const errorData = await response.json().catch(() => null);
        if (errorData && errorData.error) {
            return errorData.error;
        }
    } else {
        const errorText = await response.text().catch(() => '');
        if (errorText.trim()) {
            return errorText.trim();
        }
    }

    return `HTTP error! status: ${response.status}`;
}

export async function fetchData(url, options = {}) {
    showLoading();
    try {
        const requestOptions = { ...options };
        const method = String(requestOptions.method || 'GET').toUpperCase();
        const headers = new Headers(requestOptions.headers || {});

        if (!['GET', 'HEAD', 'OPTIONS'].includes(method) && window.CSRF_TOKEN && !headers.has('X-CSRF-Token')) {
            headers.set('X-CSRF-Token', window.CSRF_TOKEN);
        }

        requestOptions.headers = headers;

        const response = await fetch(url, requestOptions);
        if (!response.ok) {
            if (response.status === 401) {
                const loginMsg = document.getElementById('login-required-message');
                if (loginMsg) loginMsg.style.display = 'block';
                return null;
            }
            throw new Error(await parseErrorResponse(response));
        }
        return await response.json();
    } catch (error) {
        console.error("Fetch error:", error);
        alert(`Hiba történt az adatok lekérése közben: ${error.message}`);
        return null;
    } finally {
        hideLoading();
    }
}
