// Shots spec for docs-app (Docusaurus). Copied to packages/docs-app/.shots/ in
// both trees. Import only from @playwright/test; docs pages need no mocks.
// Name each file the same on both sides; that name pairs the views.
import {Locator, Page, test} from '@playwright/test';

const SHOT_DIR = process.env.SHOT_DIR!;

async function shot(page: Page, target: Locator, name: string, pad = 24) {
  await target.scrollIntoViewIfNeeded();
  await page.evaluate(() => document.fonts.ready);
  const box = await target.boundingBox();
  if (!box) {
    throw new Error(`${name}: target not visible`);
  }
  // boundingBox() is viewport-relative; a fullPage clip is document-relative.
  const scroll = await page.evaluate(() => ({x: window.scrollX, y: window.scrollY}));
  await page.screenshot({
    path: `${SHOT_DIR}/${name}.png`,
    clip: {
      x: Math.max(box.x + scroll.x - pad, 0),
      y: Math.max(box.y + scroll.y - pad, 0),
      width: box.width + pad * 2,
      height: box.height + pad * 2,
    },
    fullPage: true,
  });
}

// Scope a shot to the changed section: the heading plus everything up to the
// next heading of the same level.
const section = (page: Page, heading: string) =>
  page.locator('article .markdown').getByRole('heading', {name: heading}).locator('..');

test('01-page-section', async ({page}) => {
  await page.goto('/documentation/some/page');
  await page.locator('article').waitFor();
  await shot(page, page.locator('article'), '01-page-section');
});
