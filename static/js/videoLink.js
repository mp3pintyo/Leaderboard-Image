// Shared rendering keeps the leaderboard and comparison labels consistent.
export function createVideoLink(model) {
    const link = document.createElement('a');
    try {
        const url = new URL(model.video_url);
        if (!['https:', 'http:'].includes(url.protocol)) throw new Error('Invalid protocol');
        link.href = url.href;
    } catch {
        const unavailable = document.createElement('span');
        unavailable.className = 'text-muted';
        unavailable.textContent = 'Nincs érvényes videólink';
        return unavailable;
    }
    link.target = '_blank';
    link.rel = 'noopener noreferrer';
    link.className = `model-video-link d-inline-flex align-items-center gap-2 text-decoration-none ${model.video_is_custom ? 'text-danger fw-semibold' : 'text-secondary'}`;
    link.dataset.videoKind = model.video_is_custom ? 'custom' : 'default';
    link.title = model.video_is_custom ? 'A modellhez megadott egyedi videó' : 'Alapértelmezett link: Pinter Zsolt AI YouTube-csatornája';
    link.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="18" viewBox="0 0 24 18" aria-hidden="true" style="flex-shrink:0"><rect x="0" y="1" width="24" height="16" rx="5" fill="currentColor"/><path d="M10 5.5 16 9l-6 3.5z" fill="white"/></svg>';
    const label = document.createElement('span');
    label.textContent = model.video_is_custom ? 'Egyedi videó' : 'YouTube-csatorna';
    link.appendChild(label);
    return link;
}
