import { Page } from '@playwright/test';

type PipelineStatus = 'running' | 'completed' | 'failed' | 'paused';

/**
 * Wait for pipeline to reach a specific status
 * @param page Playwright page
 * @param status Expected pipeline status
 * @param timeout Timeout in milliseconds (default: 60000)
 */
export async function waitForPipelineStatus(
  page: Page,
  status: PipelineStatus,
  timeout: number = 60000
): Promise<void> {
  const startTime = Date.now();

  while (Date.now() - startTime < timeout) {
    // Check for status banner
    const banner = page.locator('[class*="border-b"]').filter({ hasText: /Starting|Processing|completed|failed|Waiting/ });
    
    if (await banner.isVisible({ timeout: 1000 }).catch(() => false)) {
      const text = await banner.textContent();
      
      switch (status) {
        case 'completed':
          if (text?.includes('Pipeline completed')) return;
          break;
        case 'failed':
          if (text?.includes('Pipeline failed')) return;
          break;
        case 'paused':
          if (text?.includes('concept image')) return;
          break;
        case 'running':
          if (text?.includes('Processing')) return;
          break;
      }
    }
    
    await page.waitForTimeout(1000);
  }
  
  throw new Error(`Timeout waiting for pipeline status: ${status}`);
}
