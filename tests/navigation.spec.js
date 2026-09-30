import { expect, test } from '@playwright/test';

test('Deep links open the right view and sub-view', async ({ page }) => {
    await page.goto('/#/leaderboard/matrix');
    await expect(page.locator('#leaderboard-mode')).toBeVisible();
    await expect(page.locator('#leaderboard-matrix-panel')).toBeVisible();
    await expect(page.getByRole('tab', { name: /Párharcok/ })).toHaveAttribute('aria-selected', 'true');
    await expect(page).toHaveTitle(/Leaderboard/);

    await page.goto('/#/compare?a=model-001&b=model-002');
    await expect(page.locator('#compare-mode')).toBeVisible();
    await expect(page.locator('#compare-model1-select')).toHaveValue('model-001');
    await expect(page.locator('.compare-model-card')).toHaveCount(2);

    // A vissza gomb az előző nézetre visz
    await page.goBack();
    await expect(page.locator('#leaderboard-mode')).toBeVisible();
});

test('Theme choice is applied and remembered', async ({ page, isMobile }) => {
    await page.goto('/');
    if (isMobile) await page.locator('.navbar-toggler').click();
    await page.getByRole('button', { name: 'Téma választása' }).click();
    await page.getByRole('button', { name: /Sötét/ }).click();
    await expect(page.locator('html')).toHaveAttribute('data-bs-theme', 'dark');
    await page.reload();
    await expect(page.locator('html')).toHaveAttribute('data-bs-theme', 'dark');
});

test('Battle image opens the zoomable lightbox without revealing the model', async ({ page }) => {
    await page.goto('/');
    const image = page.locator('#battle-image1');
    await expect.poll(() => image.evaluate((el) => el.complete && el.naturalWidth > 0)).toBe(true);
    await image.click();
    await expect(page.locator('#lightbox')).toBeVisible();
    await expect(page.locator('#lightbox-caption')).toHaveText(/^A oldali kép/);
    await page.locator('#lightbox-zoom-in').click();
    await expect(page.locator('#lightbox-image')).toHaveAttribute('style', /scale\(1\.5\)/);
    await page.keyboard.press('Escape');
    await expect(page.locator('#lightbox')).toBeHidden();
});

test('Security headers are sent', async ({ request }) => {
    const response = await request.get('/');
    const csp = response.headers()['content-security-policy'];
    expect(csp).toContain("script-src 'self' https://cdn.jsdelivr.net");
    expect(csp).toContain("frame-ancestors 'none'");
    expect(response.headers()['x-content-type-options']).toBe('nosniff');
});
