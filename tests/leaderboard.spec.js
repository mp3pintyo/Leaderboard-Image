import { expect, test } from '@playwright/test';
import os from 'node:os';
import path from 'node:path';

test('Leaderboard Quality vs. Price Top 10/20 flow', async ({ page }, testInfo) => {
    const browserMessages = [];
    page.on('console', (message) => {
        if (message.type() === 'error' || message.type() === 'warning') {
            browserMessages.push(`${message.type()}: ${message.text()}`);
        }
    });
    page.on('pageerror', (error) => browserMessages.push(`pageerror: ${error.message}`));

    await page.goto('/');
    await expect(page).toHaveTitle('AI Képgenerátor Aréna');
    await expect(page.locator('body')).toContainText('Arena Battle');
    await expect(page.locator('.vite-error-overlay, nextjs-portal, #webpack-dev-server-client-overlay')).toHaveCount(0);

    const navbarToggler = page.locator('.navbar-toggler');
    if (await navbarToggler.isVisible()) {
        await navbarToggler.click();
        await expect(page.locator('#navbarNav')).toHaveClass(/show/);
    }
    await page.getByRole('link', { name: 'Leaderboard', exact: true }).click();
    await expect(page.locator('#navbarNav')).not.toHaveClass(/show/);
    await expect(page.locator('#leaderboard-mode')).toBeVisible();
    await expect(page.getByRole('tab', { name: /ELO ranglista/ })).toHaveAttribute('aria-selected', 'true');
    await expect(page.locator('#leaderboard-table-body tr').first()).toBeVisible();

    const optionalColumns = [
        ['leaderboard-column-release-date', 'Megjelenés'],
        ['leaderboard-column-resolution', 'Max felbontás'],
        ['leaderboard-column-pricing', 'Árazás']
    ];
    for (const [controlId, label] of optionalColumns) {
        await expect(page.locator(`#${controlId}`)).not.toBeChecked();
        await page.locator(`label[for="${controlId}"]`).click();
        await expect(page.locator(`#${controlId}`)).toBeChecked();
        await expect(page.locator(`th[data-column-header="${controlId.replace('leaderboard-column-', '').replace('resolution', 'max_resolution').replace('release-date', 'release_date').replace('pricing', 'pricing')}"]`)).toBeVisible();
        await expect(page.locator('#leaderboard-table-body tr').first()).toContainText(label === 'Megjelenés' ? /\d{4}/ : label === 'Max felbontás' ? /\d+x\d+/ : /\$|Free|Subscription/);
    }

    await page.getByRole('tab', { name: /Minőség vs\. ár/ }).click();
    await expect(page.locator('#leaderboard-quality-price-panel')).toBeVisible();
    await expect(page.getByRole('tab', { name: /Minőség vs\. ár/ })).toHaveAttribute('aria-selected', 'true');
    await expect(page.locator('#quality-price-chart')).toBeVisible();

    const eligibleCount = await page.evaluate(async () => {
        const response = await fetch('/api/leaderboard?model_type=all');
        const rows = await response.json();
        return rows.filter((row) => Number.isFinite(row.price_per_1000)).length;
    });
    expect(eligibleCount).toBeGreaterThan(0);

    const screenshotPrefix = `leaderboard-quality-price-${testInfo.project.name}`;
    const top10Path = path.join(os.tmpdir(), `${screenshotPrefix}-top-10.png`);
    await page.locator('#leaderboard-quality-price-panel').screenshot({ path: top10Path });
    await testInfo.attach('quality-price-top-10', { path: top10Path, contentType: 'image/png' });

    await page.locator('label[for="quality-price-top-20"]').click();
    await expect(page.getByLabel('Top 20')).toBeChecked();
    await page.waitForTimeout(800);

    const canvasSize = await page.locator('#quality-price-chart').evaluate((canvas) => ({
        width: canvas.width,
        height: canvas.height
    }));
    expect(canvasSize.width).toBeGreaterThan(300);
    expect(canvasSize.height).toBeGreaterThan(300);

    const top20Path = path.join(os.tmpdir(), `${screenshotPrefix}-top-20.png`);
    await page.locator('#leaderboard-quality-price-panel').screenshot({ path: top20Path });
    await testInfo.attach('quality-price-top-20', { path: top20Path, contentType: 'image/png' });

    expect(browserMessages, browserMessages.join('\n')).toEqual([]);
});

test('Expensive model does not compress affordable prices', async ({ page }) => {
    await page.route('**/api/leaderboard?model_type=all', async (route) => {
        const response = await route.fetch();
        const rows = await response.json();
        rows.sort((a, b) => b.elo - a.elo);
        rows[4].price_per_1000 = 700;
        await route.fulfill({ response, json: rows });
    });
    await page.goto('/');
    const toggle = page.locator('.navbar-toggler');
    if (await toggle.isVisible()) await toggle.click();
    await page.getByRole('link', { name: 'Leaderboard', exact: true }).click();
    await page.getByRole('tab', { name: /Minőség vs\. ár/ }).click();
    await expect.poll(() => page.evaluate(() => {
        const chart = window.Chart.getChart('quality-price-chart');
        if (!chart) return false;
        const x = chart.scales.x;
        const spacing = (a, b) => x.getPixelForValue(b) - x.getPixelForValue(a);
        return chart.data.datasets.some((dataset) => dataset.data.some((point) => point.x === 700))
            && x.max >= 700
            && spacing(10, 100) / x.width > 0.4
            && Math.abs(spacing(10, 20) - spacing(100, 200)) < 0.01;
    })).toBe(true);
});
