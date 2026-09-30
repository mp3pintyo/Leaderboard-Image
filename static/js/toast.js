// Nem blokkoló értesítések (az alert() helyett)
let container = null;

function getContainer() {
    if (!container) {
        container = document.createElement('div');
        container.className = 'toast-container position-fixed bottom-0 end-0 p-3';
        container.setAttribute('aria-live', 'polite');
        container.setAttribute('aria-atomic', 'false');
        document.body.appendChild(container);
    }
    return container;
}

/**
 * @param {string} message
 * @param {'info'|'success'|'warning'|'danger'} variant
 */
export function showToast(message, variant = 'info', { delay = 5000 } = {}) {
    const toast = document.createElement('div');
    toast.className = `toast align-items-center border-0 text-bg-${variant}`;
    toast.setAttribute('role', variant === 'danger' ? 'alert' : 'status');

    const wrapper = document.createElement('div');
    wrapper.className = 'd-flex';
    const body = document.createElement('div');
    body.className = 'toast-body';
    body.textContent = message;
    const close = document.createElement('button');
    close.type = 'button';
    close.className = `btn-close ${variant === 'warning' ? '' : 'btn-close-white'} me-2 m-auto`;
    close.setAttribute('aria-label', 'Bezárás');
    close.dataset.bsDismiss = 'toast';
    wrapper.append(body, close);
    toast.appendChild(wrapper);
    getContainer().appendChild(toast);

    if (window.bootstrap?.Toast) {
        const instance = new window.bootstrap.Toast(toast, { delay });
        toast.addEventListener('hidden.bs.toast', () => toast.remove(), { once: true });
        instance.show();
    } else {
        toast.classList.add('show');
        close.addEventListener('click', () => toast.remove());
        setTimeout(() => toast.remove(), delay);
    }
}
