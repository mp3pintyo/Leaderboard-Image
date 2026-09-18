import { expect, test } from '@playwright/test';

const channel = 'https://www.youtube.com/@pinterzsoltai';
const custom = 'https://www.youtube.com/watch?v=test-model-video';

async function navigate(page, name) {
    const toggle = page.locator('.navbar-toggler');
    if (await toggle.isVisible()) await toggle.click();
    await page.getByRole('link', { name, exact: true }).click();
}

test('Video column persists and distinguishes channel and model video', async ({ page, request }) => {
    const response = await request.get('/api/leaderboard');
    const models = await response.json();
    expect(models.length).toBeGreaterThan(0);
    expect(models.every(model => model.video_url === channel && !model.video_is_custom)).toBe(true);
    await page.route('**/api/leaderboard?*', async route => {
        const response = await route.fetch();
        const rows = await response.json();
        rows[0].video_url = custom;
        rows[0].video_is_custom = true;
        await route.fulfill({ response, json: rows });
    });
    await page.goto('/');
    await navigate(page, 'Leaderboard');
    await expect(page.locator('[data-column-header="video_url"]')).toBeHidden();
    await page.locator('label[for="leaderboard-column-video"]').click();
    const links = page.locator('#leaderboard-table-body .model-video-link');
    await expect(links.first()).toHaveText('Egyedi videó');
    await expect(links.first()).toHaveAttribute('href', custom);
    await expect(links.first()).toHaveAttribute('target', '_blank');
    await expect(links.nth(1)).toHaveText('YouTube-csatorna');
    await expect(links.nth(1)).toHaveAttribute('href', channel);
    await expect(links.first().locator('svg')).toBeVisible();
    await page.reload();
    await navigate(page, 'Leaderboard');
    await expect(page.locator('#leaderboard-column-video')).toBeChecked();
    await expect(links.first()).toBeVisible();
    await page.locator('label[for="leaderboard-column-video"]').click();
    await expect(links).toHaveCount(0);
});

test('Comparison shows both video link types', async ({ page, request }) => {
    const response = await request.get('/api/model_info?model1=model-001&model2=model-002');
    const data = await response.json();
    expect(data.model1.video_url).toBe(channel);
    expect(data.model2.video_is_custom).toBe(false);
    await page.route('**/api/model_info?*', async route => {
        const response = await route.fetch();
        const data = await response.json();
        data.model1.video_url = custom;
        data.model1.video_is_custom = true;
        await route.fulfill({ response, json: data });
    });
    await page.goto('/');
    await navigate(page, 'Összehasonlítás');
    await page.locator('#compare-load-btn').click();
    const cards = page.locator('.compare-model-card');
    await expect(cards.first().locator('.model-video-link')).toHaveText('Egyedi videó');
    await expect(cards.first().locator('.model-video-link')).toHaveAttribute('href', custom);
    await expect(cards.nth(1).locator('.model-video-link')).toHaveText('YouTube-csatorna');
    await expect(cards.nth(1).locator('.model-video-link')).toHaveAttribute('href', channel);
});
