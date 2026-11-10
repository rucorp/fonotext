// npm ci --prefix tools/og && npx --prefix tools/og playwright install chromium
// bash tools/og/render-og.sh
// CHROME_BIN may point to an existing Chrome/Chromium instead.
import { chromium } from 'playwright';
import { createServer } from 'node:http';
import { readFile, mkdir } from 'node:fs/promises';
import { dirname, resolve, extname, sep } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '../..');
const mime = { '.html': 'text/html', '.css': 'text/css', '.js': 'text/javascript', '.svg': 'image/svg+xml', '.png': 'image/png', '.ttf': 'font/ttf', '.wav': 'audio/wav' };
const server = createServer(async (req, res) => {
  const path = resolve(root, '.' + decodeURIComponent(new URL(req.url, 'http://localhost').pathname));
  if (!path.startsWith(root + sep)) { res.writeHead(403).end(); return; }
  try {
    const data = await readFile(path);
    res.writeHead(200, { 'Content-Type': mime[extname(path)] || 'application/octet-stream' }).end(data);
  } catch { res.writeHead(404).end(); }
});
await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
const base = `http://127.0.0.1:${server.address().port}`;
let browser;
try {
  await mkdir(resolve(root, 'docs/social'), { recursive: true });
  browser = await chromium.launch({
    ...(process.env.CHROME_BIN ? { executablePath: process.env.CHROME_BIN } : {}),
    args: ['--no-sandbox', '--disable-dev-shm-usage'],
  });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 }, deviceScaleFactor: 1, locale: 'ru-RU', reducedMotion: 'reduce' });
  await page.goto(`${base}/docs/index.html`, { waitUntil: 'load' });
  await page.evaluate(() => document.fonts.ready);
  await page.locator('.fxa-chart').waitFor();
  const headline = await page.locator('h1').innerText();
  await page.screenshot({ path: resolve(root, 'docs/social/homepage.png'), clip: { x: 0, y: 0, width: 1440, height: 824 }, animations: 'disabled' });
  await page.locator('.fxa-card').first().screenshot({ path: resolve(root, 'docs/social/demo-call.png'), animations: 'disabled' });
  for (const [file, width, height, cls] of [
    ['og-image.png', 1200, 630, ''],
    ['social/square-1080.png', 1080, 1080, 'portrait'],
    ['social/stories-1080x1920.png', 1080, 1920, 'portrait story'],
    ['social/vk-cover-1590x400.png', 1590, 400, 'wide'],
    ['social/linkedin-1584x396.png', 1584, 396, 'wide'],
  ]) {
    await page.setViewportSize({ width, height });
    await page.goto(`${base}/tools/og/og-hero.html`, { waitUntil: 'load' });
    await page.evaluate(({ cls, headline }) => {
      document.body.className = cls;
      document.querySelector('h1').textContent = headline.replace(/\s+/g, ' ');
    }, { cls, headline });
    await page.evaluate(() => document.fonts.ready);
    await page.screenshot({ path: resolve(root, 'docs', file), animations: 'disabled' });
    console.log(`${file}: ${width}×${height}`);
  }
} finally {
  await browser?.close();
  await new Promise(resolve => server.close(resolve));
}
