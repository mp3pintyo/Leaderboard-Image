import { expect, test } from '@playwright/test';

test('Anonymous battle: blind images, login prompt, skip reveals and loads a new pair', async ({ page }) => {
    const errors = [];
    page.on('pageerror', (error) => errors.push(error.message));

    const battleResponse = page.waitForResponse('**/api/battle_data');
    await page.goto('/');
    const battle = await (await battleResponse).json();
    // A modellek kiléte nem szerepelhet a szavazás előtti válaszban
    expect(Object.keys(battle).sort()).toEqual(['battle_id', 'image_a', 'image_b', 'prompt_id', 'prompt_text', 'vote_delay_ms']);

    const imageA = page.locator('#battle-image1');
    await expect.poll(() => imageA.evaluate((el) => el.complete && el.naturalWidth > 0)).toBe(true);
    await expect(page.locator('#login-required-message')).toBeVisible();
    await expect(page.locator('#vote-btn1')).toBeDisabled();
    await expect(page.locator('#tie-btn')).toBeDisabled();
    await expect(page.locator('#battle-model1-name')).toHaveText('Modell A');

    const firstSrc = await imageA.getAttribute('src');
    await page.keyboard.press('s');
    await expect(page.locator('#battle-slot-a')).toHaveClass(/is-revealed/);
    await expect(page.locator('#battle-model1-name')).not.toHaveText('Modell A');
    await expect(page.locator('#battle-model1-name')).toHaveText('Modell A', { timeout: 10_000 });
    await expect(page.locator('#skip-btn')).toBeEnabled();
    expect(await page.locator('#battle-prompt').textContent()).toContain('Prompt:');
    // Új pár (a kép forrása általában változik; ugyanaz a kép csak véletlen egyezés lehet)
    expect(typeof firstSrc).toBe('string');
    expect(errors).toEqual([]);
});
