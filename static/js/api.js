// API hívások és közös függvények
export const loadingIndicator = document.getElementById('loading-indicator');

export function showLoading() {
    loadingIndicator.style.display = 'block';
}

export function hideLoading() {
    loadingIndicator.style.display = 'none';
}

export async function fetchData(url, options = {}) {
    showLoading();
    try {
        const response = await fetch(url, options);
        if (!response.ok) {
            if (response.status === 401) {
                const loginMsg = document.getElementById('login-required-message');
                if (loginMsg) loginMsg.style.display = 'block';
                return null;
            }
            const errorData = await response.json();
            throw new Error(errorData.error || `HTTP error! status: ${response.status}`);
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
