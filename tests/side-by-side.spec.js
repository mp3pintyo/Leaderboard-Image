import { expect, test } from '@playwright/test';
import os from 'node:os';
import path from 'node:path';

test('Side-by-Side shows every selected image on mobile and desktop', async ({ page, isMobile }) => {
    const image = index => `data:image/svg+xml,${encodeURIComponent(`<svg xmlns="http://www.w3.org/2000/svg" width="800" height="800"><rect width="800" height="800" fill="${['red', 'green', 'blue'][index]}"/></svg>`)}`;
    await page.route('**/api/side_by_side_data?*', route => {
        const params = new URL(route.request().url()).searchParams;
        const json = {
            prompt_id: 'test-prompt',
            prompt_text: 'Mobil képek ellenőrzése',
            model1: { name: 'Modell 1', image_url: image(0) },
            model2: { name: 'Modell 2', image_url: image(1) }
        };
        if (params.get('model3')) json.model3 = { name: 'Modell 3', image_url: image(2) };
        return route.fulfill({ json });
    });

    await page.goto('/');
    if (isMobile) await page.locator('.navbar-toggler').click();
    await page.getByRole('link', { name: 'Side-by-Side' }).click();
    if (isMobile) await expect(page.locator('#navbarNav')).toBeHidden();
    await expect(page.locator('#sbs-model3-container')).toBeHidden();

    await page.locator('#sbs-model3-select').selectOption({ index: 3 });
    await page.locator('#sbs-load-btn').click();

    for (const index of [1, 2, 3]) {
        const img = page.locator(`#sbs-image${index}`);
        await expect(img).toBeVisible();
        await expect.poll(() => img.evaluate(el => el.complete && el.naturalWidth > 0)).toBe(true);
        if (isMobile) {
            await img.scrollIntoViewIfNeeded();
            const box = await img.boundingBox();
            expect(box.y).toBeGreaterThanOrEqual(0);
            expect(box.y + box.height).toBeLessThanOrEqual(page.viewportSize().height + 1);
        }
    }

    if (isMobile) {
        await page.evaluate(() => window.scrollTo(0, 0));
        await page.screenshot({ path: path.join(os.tmpdir(), 'leaderboard-side-by-side-mobile.png'), fullPage: true });
    }

    await page.locator('#sbs-model3-select').selectOption('');
    await expect(page.locator('#sbs-model3-container')).toBeHidden();
});
