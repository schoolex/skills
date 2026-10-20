// Headless smoke test for a single-file explorer. Worked example: the PostHog event graph.
// Usage: PW=<dir containing node_modules/playwright> node verify.example.js <file.html> [outDir]
// Adapt the selectors and assertions below to the explorer's own feature list.
const path = require('path');
const { chromium } = require(path.join(process.env.PW || process.cwd(), 'node_modules/playwright'));
const FILE = path.resolve(process.argv[2]);
const URL = 'file://' + FILE;
const OUT = (process.argv[3] || require('os').tmpdir()) + '/';
(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1500, height: 900 } });
  const errors = [];
  page.on('pageerror', e => errors.push('pageerror: ' + e.message));
  page.on('console', m => { if (m.type() === 'error' || m.type() === 'warning') errors.push(m.type() + ': ' + m.text()); });
  await page.goto(URL);
  await page.waitForTimeout(400);
  const r = {};
  r.nodes = await page.locator('.node').count();
  r.edges = await page.locator('path.edge').count();
  r.count = await page.textContent('#count');
  await page.screenshot({ path: OUT + '1-overview.png' });

  // Select via search
  await page.keyboard.press('/');
  await page.keyboard.type('data_request_submitted');
  r.hits = await page.locator('#results [data-i]').count();
  await page.keyboard.press('Enter');
  await page.waitForTimeout(600);
  r.drawerOpen = await page.locator('#detail.open').count();
  r.selTitle = await page.textContent('#detail h3');
  r.hiEdges = await page.locator('path.edge.hi').count();
  // Full path depth
  await page.click('#depth button[data-d="99"]');
  r.hiEdgesFull = await page.locator('path.edge.hi').count();
  r.hash = await page.evaluate(() => location.hash);
  await page.screenshot({ path: OUT + '2-selected.png' });

  // Jump via link in drawer
  await page.click('#detail [data-go="data_request_internal_approved"]');
  await page.waitForTimeout(600);
  r.afterJump = await page.textContent('#detail h3');

  // Toggle PR filter + hide lane
  await page.keyboard.press('Escape');
  r.drawerAfterEsc = await page.locator('#detail.open').count();
  await page.click('#prChips .chip:nth-child(1)');
  r.countNoMain = await page.textContent('#count');
  await page.hover('#lanes li[data-g="global"]');
  await page.click('#lanes li[data-g="global"] .eye');
  r.nodesAfterHide = await page.locator('.node').count();

  // Zoom, theme
  await page.click('#zi');
  r.pct = await page.textContent('#pct');
  await page.keyboard.press('t');
  r.theme = await page.evaluate(() => document.documentElement.dataset.theme);
  await page.mouse.move(700, 400);
  await page.screenshot({ path: OUT + '3-dark.png' });

  // Deep link restore
  const p2 = await browser.newPage({ viewport: { width: 1500, height: 900 } });
  p2.on('pageerror', e => errors.push('p2 pageerror: ' + e.message));
  await p2.goto(URL + '#e=ai_chatbot_message_sent&hide=admin');
  await p2.waitForTimeout(600);
  r.deepLink = await p2.textContent('#detail h3');
  r.deepNodes = await p2.locator('.node').count();
  // Hover tooltip
  await p2.hover('.node.sel');
  r.tip = await p2.locator('#tip.on').count();
  await p2.screenshot({ path: OUT + '4-deeplink.png' });

  console.log(JSON.stringify(r, null, 1));
  console.log('ERRORS:', errors.length ? errors.join('\n') : 'none');
  await browser.close();
})();
