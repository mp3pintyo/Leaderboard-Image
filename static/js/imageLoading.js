/**
 * Download and decode an image before it replaces the one currently visible.
 * The browser remains responsible for its HTTP/memory cache; this helper
 * prevents an empty frame while a cached or network response is decoded.
 */
export async function preloadImage(url) {
    if (!url) {
        throw new Error('Missing image URL');
    }

    const image = new Image();
    image.decoding = 'async';
    image.src = url;

    if (typeof image.decode === 'function') {
        try {
            await image.decode();
            return;
        } catch (error) {
            // Some browsers reject decode() even though the normal load event
            // still succeeds, so fall through to the event-based check.
            if (image.complete && image.naturalWidth > 0) {
                return;
            }
        }
    }

    await new Promise((resolve, reject) => {
        if (image.complete) {
            if (image.naturalWidth > 0) resolve();
            else reject(new Error(`Image failed to load: ${url}`));
            return;
        }

        image.addEventListener('load', resolve, { once: true });
        image.addEventListener('error', () => reject(new Error(`Image failed to load: ${url}`)), { once: true });
    });
}

export function preloadImages(urls) {
    return Promise.all(urls.map(preloadImage));
}
