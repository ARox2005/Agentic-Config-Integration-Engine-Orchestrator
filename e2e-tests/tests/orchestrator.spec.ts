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

});
