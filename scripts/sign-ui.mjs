import fs from 'node:fs/promises';
import { chromium } from 'playwright';
const base = 'http://127.0.0.1:18069';
const accounts = JSON.parse(await fs.readFile('runtime/accounts.json', 'utf8'));
const targets = JSON.parse(await fs.readFile('runtime/signers.json', 'utf8'));
const keys = process.argv.slice(2);
const browser = await chromium.launch({headless: true});
try {
  for (const key of keys) {
    const context = await browser.newContext();
    await context.route('**/*', route => {
      const url = new URL(route.request().url());
      return ['127.0.0.1', 'localhost'].includes(url.hostname) || ['data:', 'blob:'].includes(url.protocol) ? route.continue() : route.abort();
    });
    const a = accounts[key];
    const auth = await context.request.post(base + '/web/session/authenticate', {data: {jsonrpc: '2.0', id: 1, params: {db: 'packaging_poc', login: a.login, password: a.password}}});
    if ((await auth.json()).result?.uid !== a.uid) throw new Error('fixture_authentication_failed');
    const target = targets[key];
    const page = await context.newPage();
    // Save only token-redacted errors.
    page.on('pageerror', error => fs.appendFile('runtime/ui-errors.log', error.message.replace(/[a-f0-9-]{32,}/gi, '[REDACTED]') + '\n'));
    await page.goto(`${base}/sign_oca/document/${target.signerId}/${target.token}`, {waitUntil: 'networkidle'});
    await page.screenshot({path: `artifacts/${key}-ui-before.png`, fullPage: true});
    const frame = page.frameLocator('iframe');
    await frame.locator(`[data-field="${key === 'alice' ? 1 : 2}"]`).click({timeout: 60000});
    await page.getByRole('button', {name: /adopt|sign|apply/i}).last().click();
    await page.screenshot({path: `artifacts/${key}-ui-filled.png`, fullPage: true});
    await page.locator('#sign_oca_button').click();
    await page.waitForLoadState('networkidle');
    await page.screenshot({path: `artifacts/${key}-ui-complete.png`, fullPage: true});
    console.log(`OCA UI journey completed for synthetic ${key}`);
    await context.close();
  }
} finally { await browser.close(); }
