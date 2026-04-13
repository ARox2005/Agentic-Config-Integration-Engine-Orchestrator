import { test, expect } from '@playwright/test';

test.describe('FinSpark Orchestrator Workflow', () => {

  test('[C46] Orchestrator UI loads successfully', async ({ page }) => {
    // Navigate to the Orchestrator Frontend (it uses the baseURL we set earlier)
    await page.goto('/');

    // Assert 1: Check if the application title is correct
    await expect(page).toHaveTitle(/Orchestrator/i);

    // Assert 2: Check if the main heading is visible
    const heading = page.getByRole('heading', { name: "ZeroOne AI Orchestrator" });
    await expect(heading).toBeVisible();

    // Assert 3: Verify the "Generate Blueprint" button exists
    const generateBtn = page.getByRole('button', { name: /Generate Blueprint/i });
    await expect(generateBtn).toBeVisible();
  });

  test('[C47] Theme toggle button is visible', async ({ page }) => {
    await page.goto('/');
    const themeBtn = page.locator('.theme-toggle-btn');
    await expect(themeBtn).toBeVisible();
  })

  test('[C48] Theme switches to light mode', async ({ page }) => {
    await page.goto('/');
    const themeBtn = page.locator('.theme-toggle-btn');
    await themeBtn.click();
    const dataTheme = await page.locator('html').getAttribute('data-theme');
    expect(dataTheme).toBe('light');
  })

  test('[C49] Help button opens instructions modal', async ({ page }) => {
    await page.goto('/');
    const helpBtn = page.locator('.help-btn');
    await helpBtn.click();

    const modal = page.locator('.modal-overlay');
    await expect(modal).toBeVisible();

    const modalTitle = page.locator('.modal-content h2');
    await expect(modalTitle).toHaveText('How to Use the Orchestrator');
  })

  test('[C50] Instructions modal can be closed', async ({ page }) => {
    await page.goto('/');
    const helpBtn = page.locator('.help-btn');
    await helpBtn.click();

    const modal = page.locator('.modal-overlay');
    await expect(modal).toBeVisible();

    const modalClose = page.locator('.modal-close')
    await modalClose.click();

    await expect(modal).not.toBeVisible();
  })
});
