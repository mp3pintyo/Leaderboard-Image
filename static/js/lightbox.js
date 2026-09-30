// Teljes képernyős képnézegető nagyítással (görgő, +/−, dupla kattintás, csípés) és mozgatással (húzás)
const modalElement = document.getElementById('lightbox');
const stage = document.getElementById('lightbox-stage');
const image = document.getElementById('lightbox-image');
const caption = document.getElementById('lightbox-caption');
const prevBtn = document.getElementById('lightbox-prev');
const nextBtn = document.getElementById('lightbox-next');
const zoomInBtn = document.getElementById('lightbox-zoom-in');
const zoomOutBtn = document.getElementById('lightbox-zoom-out');
const resetBtn = document.getElementById('lightbox-reset');
const openOriginal = document.getElementById('lightbox-original');

const MIN_SCALE = 1;
const MAX_SCALE = 8;

let items = [];
let index = 0;
let scale = 1;
let tx = 0;
let ty = 0;
const pointers = new Map();
let dragStart = null;
let pinchStart = null;

function getModal() {
    return window.bootstrap?.Modal ? window.bootstrap.Modal.getOrCreateInstance(modalElement) : null;
}

function applyTransform() {
    image.style.transform = `translate(${tx}px, ${ty}px) scale(${scale})`;
    stage.classList.toggle('is-zoomed', scale > 1.001);
    zoomOutBtn.disabled = scale <= MIN_SCALE;
    zoomInBtn.disabled = scale >= MAX_SCALE;
}

function clampTranslation() {
    // Ne lehessen a képet teljesen kitolni a látható területből
    const rect = stage.getBoundingClientRect();
    const maxX = (rect.width * (scale - 1)) / 2;
    const maxY = (rect.height * (scale - 1)) / 2;
    tx = Math.min(maxX, Math.max(-maxX, tx));
    ty = Math.min(maxY, Math.max(-maxY, ty));
}

/** Nagyítás úgy, hogy a (clientX, clientY) pont a helyén maradjon. */
function zoomTo(newScale, clientX, clientY) {
    const rect = stage.getBoundingClientRect();
    const target = Math.min(MAX_SCALE, Math.max(MIN_SCALE, newScale));
    const px = (clientX ?? rect.left + rect.width / 2) - rect.left - rect.width / 2;
    const py = (clientY ?? rect.top + rect.height / 2) - rect.top - rect.height / 2;
    const ratio = target / scale;
    tx = px - ratio * (px - tx);
    ty = py - ratio * (py - ty);
    scale = target;
    if (scale === MIN_SCALE) {
        tx = 0;
        ty = 0;
    }
    clampTranslation();
    applyTransform();
}

function resetZoom() {
    scale = 1;
    tx = 0;
    ty = 0;
    applyTransform();
}

function show(newIndex) {
    index = (newIndex + items.length) % items.length;
    const item = items[index];
    resetZoom();
    image.src = item.src;
    image.alt = item.caption || 'Nagyított kép';
    caption.textContent = items.length > 1 ? `${item.caption} (${index + 1}/${items.length})` : item.caption;
    openOriginal.href = item.src;
    prevBtn.hidden = nextBtn.hidden = items.length < 2;
}

/**
 * @param {{src: string, caption: string}[]} list
 * @param {number} startIndex
 */
export function openLightbox(list, startIndex = 0) {
    items = list.filter((item) => item.src);
    if (!items.length || !getModal()) return;
    show(Math.min(startIndex, items.length - 1));
    getModal().show();
}

/** Kattintásra nagyíthatóvá teszi a megadott képeket; a getCaption az aktuális feliratot adja. */
export function bindLightbox(images, getCaption) {
    const list = [...images];
    list.forEach((img, position) => {
        img.addEventListener('click', () => {
            if (!img.getAttribute('src')) return;
            const available = list.filter((el) => el.getAttribute('src') && el.offsetParent !== null);
            openLightbox(
                available.map((el) => ({ src: el.currentSrc || el.src, caption: getCaption(el, list.indexOf(el)) })),
                Math.max(0, available.indexOf(img)),
            );
        });
        if (!img.hasAttribute('tabindex')) img.tabIndex = 0;
        img.addEventListener('keydown', (event) => {
            if (event.key === 'Enter') {
                event.preventDefault();
                img.click();
            }
        });
        img.dataset.lightboxIndex = String(position);
    });
}

export function initLightbox() {
    if (!modalElement) return;

    stage.addEventListener('wheel', (event) => {
        event.preventDefault();
        zoomTo(scale * (event.deltaY < 0 ? 1.2 : 1 / 1.2), event.clientX, event.clientY);
    }, { passive: false });

    stage.addEventListener('dblclick', (event) => {
        zoomTo(scale > 1.001 ? 1 : 2.5, event.clientX, event.clientY);
    });

    stage.addEventListener('pointerdown', (event) => {
        stage.setPointerCapture(event.pointerId);
        pointers.set(event.pointerId, { x: event.clientX, y: event.clientY });
        if (pointers.size === 1) {
            dragStart = { x: event.clientX, y: event.clientY, tx, ty };
        } else if (pointers.size === 2) {
            const [a, b] = [...pointers.values()];
            pinchStart = { distance: Math.hypot(a.x - b.x, a.y - b.y), scale };
            dragStart = null;
        }
    });

    stage.addEventListener('pointermove', (event) => {
        if (!pointers.has(event.pointerId)) return;
        pointers.set(event.pointerId, { x: event.clientX, y: event.clientY });
        if (pointers.size === 2 && pinchStart) {
            const [a, b] = [...pointers.values()];
            const distance = Math.hypot(a.x - b.x, a.y - b.y);
            zoomTo(pinchStart.scale * (distance / pinchStart.distance), (a.x + b.x) / 2, (a.y + b.y) / 2);
        } else if (dragStart && scale > 1.001) {
            stage.classList.add('is-dragging');
            tx = dragStart.tx + (event.clientX - dragStart.x);
            ty = dragStart.ty + (event.clientY - dragStart.y);
            clampTranslation();
            applyTransform();
        }
    });

    const endPointer = (event) => {
        pointers.delete(event.pointerId);
        if (pointers.size < 2) pinchStart = null;
        if (pointers.size === 0) {
            dragStart = null;
            stage.classList.remove('is-dragging');
        }
    };
    stage.addEventListener('pointerup', endPointer);
    stage.addEventListener('pointercancel', endPointer);

    zoomInBtn.addEventListener('click', () => zoomTo(scale * 1.5));
    zoomOutBtn.addEventListener('click', () => zoomTo(scale / 1.5));
    resetBtn.addEventListener('click', resetZoom);
    prevBtn.addEventListener('click', () => show(index - 1));
    nextBtn.addEventListener('click', () => show(index + 1));

    modalElement.addEventListener('keydown', (event) => {
        if (event.key === 'ArrowLeft' && items.length > 1) show(index - 1);
        else if (event.key === 'ArrowRight' && items.length > 1) show(index + 1);
        else if (event.key === '+' || event.key === '=') zoomTo(scale * 1.5);
        else if (event.key === '-') zoomTo(scale / 1.5);
        else if (event.key === '0') resetZoom();
        else return;
        event.preventDefault();
        event.stopPropagation();
    });
    modalElement.addEventListener('hidden.bs.modal', () => {
        image.removeAttribute('src');
        resetZoom();
    });
    window.addEventListener('resize', () => {
        clampTranslation();
        applyTransform();
    });
}
