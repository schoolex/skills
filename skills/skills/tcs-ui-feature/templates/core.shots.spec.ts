// Shots spec for core-app. Copied to packages/core-app/playwright/.shots/ in
// BOTH the before and after trees, so:
//   - import only fixtures/helpers/test IDs that exist at the base commit too
//   - locate views by anchors present on both sides (an existing test ID,
//     section heading, or label), never by an ID this change introduces
//   - give each view the same file name on both sides; that is the pairing key
import {Locator, Page, test} from '@playwright/test';

// Paths are relative to packages/core-app/playwright/.shots/
import {
  mockCommonRequestsPageApis,
  mockRequestDetail,
  USER_DR_PAGE_ROUTE,
  visitRequestsPage,
} from '../integration/pages/RequestsPage/requestsPageHelpers';
import {normalUser} from '../fixtures/users';

const SHOT_DIR = process.env.SHOT_DIR!;

// Element shot of the changed region, padded so surrounding layout is visible.
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

// One test per view. Same fixture data on both sides.
test('01-detail-page-section', async ({page}) => {
  const request = {/* fixture that exercises the change */} as never;
  await mockCommonRequestsPageApis(page);
  await mockRequestDetail(page, request);
  await visitRequestsPage(page, normalUser, USER_DR_PAGE_ROUTE('id'));
  await shot(page, page.getByText('Section heading on both sides'), '01-detail-page-section');
});
