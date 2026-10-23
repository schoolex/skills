// Pair <out>/before/*.png with <out>/after/*.png and write, per view:
//   <out>/<name>.compare.png  - labelled side-by-side, for the PR body
//   <out>/index.html          - all pairs, for the human to eyeball
// Usage: node compose.mjs <repo> <out> <beforeLabel> <afterLabel>
import {existsSync, readdirSync, readFileSync, writeFileSync} from 'fs';
import {createRequire} from 'module';
import {join} from 'path';

const [repo, out, beforeLabel, afterLabel] = process.argv.slice(2);
const {chromium} = createRequire(join(repo, 'package.json'))('playwright');

const list = side =>
  existsSync(join(out, side))
    ? readdirSync(join(out, side)).filter(f => f.endsWith('.png'))
    : [];
const before = new Set(list('before'));
const after = new Set(list('after'));
const names = [...new Set([...before, ...after])].sort();
if (names.length === 0) {
  console.error('compose: no screenshots captured; check the spec output above');
  process.exit(1);
}

const dataUri = (side, f) =>
  `data:image/png;base64,${readFileSync(join(out, side, f)).toString('base64')}`;
const cell = (side, f, label) => `
  <figure class="${side}">
    <figcaption>${label}</figcaption>
    ${
      (side === 'before' ? before : after).has(f)
        ? `<img src="${dataUri(side, f)}">`
        : `<div class="missing">not captured on this side</div>`
    }
  </figure>`;
const css = `
  body{margin:0;font:14px -apple-system,system-ui,sans-serif;background:#fff;color:#111}
  .pair{display:flex;gap:16px;padding:16px;align-items:flex-start}
  figure{margin:0;flex:1;min-width:0}
  figcaption{font-weight:600;padding:6px 10px;border-radius:4px 4px 0 0;color:#fff}
  .before figcaption{background:#b42318}.after figcaption{background:#067647}
  img{display:block;max-width:100%;border:1px solid #d0d5dd;border-top:0}
  .missing{padding:40px;border:1px dashed #d0d5dd;color:#667085;text-align:center}
  h2{font-size:15px;margin:24px 16px 0;font-family:ui-monospace,monospace}`;
const pairHtml = f =>
  `<div class="pair">${cell('before', f, beforeLabel)}${cell('after', f, afterLabel)}</div>`;

// PNG width lives in the IHDR chunk at byte 16.
const pngWidth = (side, f) =>
  readFileSync(join(out, side, f)).readUInt32BE(16);
const sideWidth = (side, f) =>
  (side === 'before' ? before : after).has(f) ? pngWidth(side, f) : 400;

const browser = await chromium.launch();
const page = await browser.newPage({viewport: {width: 1600, height: 400}});
const rows = [];
for (const f of names) {
  const stem = f.replace(/\.png$/, '');
  // Size the canvas so neither side is scaled down.
  const w = Math.max(sideWidth('before', f), sideWidth('after', f));
  await page.setViewportSize({width: w * 2 + 48 + 2, height: 400});
  await page.setContent(`<style>${css}</style>${pairHtml(f)}`);
  await page.locator('.pair').screenshot({path: join(out, `${stem}.compare.png`)});
  const status = !before.has(f) ? 'after only' : !after.has(f) ? 'before only' : 'pair';
  rows.push({stem, status});
}
await browser.close();

writeFileSync(
  join(out, 'index.html'),
  `<!doctype html><title>before/after</title><style>${css}</style>` +
    names.map(f => `<h2>${f.replace(/\.png$/, '')}</h2>${pairHtml(f)}`).join('')
);

for (const {stem, status} of rows) {
  console.log(`compose: ${status.padEnd(11)} ${join(out, `${stem}.compare.png`)}`);
}
console.log(`compose: index        ${join(out, 'index.html')}`);
