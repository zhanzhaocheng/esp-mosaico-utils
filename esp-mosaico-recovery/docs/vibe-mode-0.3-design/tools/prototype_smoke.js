// Playwright smoke coverage for the Vibe Mode v6 single-file prototype.
// Usage: node tools/prototype_smoke.js [screenshot-dir]
// Set PLAYWRIGHT_MODULE if Playwright is installed outside this directory.
const path = require('path');
const fs = require('fs');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');

const pageFile = path.resolve(__dirname, '..', 'prototype', 'index.html');
const out = process.argv[2] || null;
if (out) fs.mkdirSync(out, { recursive: true });
let pass = 0;
let fail = 0;
const check = (condition, message) => {
  if (condition) pass++; else fail++;
  console.log(`${condition ? 'PASS' : 'FAIL'} ${message}`);
};

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1280, height: 1000 } });
  const errors = [];
  page.on('pageerror', (error) => errors.push(`pageerror: ${error.message}`));
  page.on('console', (message) => {
    if (message.type() === 'error') errors.push(`console: ${message.text()}`);
  });
  await page.goto(`file://${pageFile}`);
  await page.waitForTimeout(400);

  // The live page is the last .page layer; the leaving one is removed after the slide.
  const loc = (name) => page.locator(`#screen [data-name="${name}"]`).last();
  const has = async (name) => (await page.locator(`#screen [data-name="${name}"]`).count()) > 0;
  const text = async (name) => ((await loc(name).textContent().catch(() => null)) || '').trim();
  const view = () => page.evaluate(() => cur().view);
  const toastText = async () => ((await page.locator('#screen .toast-layer').textContent().catch(() => '')) || '').trim();
  const settle = (ms = 340) => page.waitForTimeout(ms);
  const tap = async (name, wait = 340) => { await loc(name).click(); await settle(wait); };
  const panel = async (id, wait = 240) => { await page.locator(`#${id}`).click(); await settle(wait); };
  const blur = () => page.evaluate(() => document.activeElement?.blur());
  const ai = async (ms = 55, wait = 140) => {
    await blur();
    await page.keyboard.down('ArrowUp');
    await page.waitForTimeout(ms);
    await page.keyboard.up('ArrowUp');
    await page.waitForTimeout(wait);
  };
  const aiDouble = async () => { await ai(55, 60); await ai(55, 420); };
  const reset = async () => { await panel('simReset', 420); await page.evaluate(() => hideToast()); };
  const rows = (kind) => page.locator(`#screen .row-hit[data-row^="${kind}:"]`);
  const rowLabels = async (kind) => rows(kind).evaluateAll((els) => els.map((e) => e.getAttribute('aria-label')));
  const center = async (name) => {
    const box = await loc(name).boundingBox();
    return { x: box.x + box.width / 2, y: box.y + box.height / 2 };
  };
  const hold = async (name, ms = 700) => {
    const c = await center(name);
    await page.mouse.move(c.x, c.y);
    await page.mouse.down();
    await page.waitForTimeout(ms);
    await page.mouse.up();
    await settle(380);
  };
  const screenBox = async () => page.locator('#screen').boundingBox();
  const drag = async (x0, y0, x1, y1, steps = 8, wait = 420) => {
    const b = await screenBox(), k = b.width / 480;
    await page.mouse.move(b.x + x0 * k, b.y + y0 * k);
    await page.mouse.down();
    for (let i = 1; i <= steps; i++) await page.mouse.move(b.x + (x0 + (x1 - x0) * i / steps) * k, b.y + (y0 + (y1 - y0) * i / steps) * k);
    await page.mouse.up();
    await settle(wait);
  };
  const typeKeys = async (s) => { await blur(); for (const ch of s) await page.keyboard.press(ch); };
  const shot = async (name) => { if (out) await page.locator('#screen').screenshot({ path: path.join(out, `${name}.png`) }); };

  // 1. Load, tokens and gallery.
  check(errors.length === 0, 'loads without script errors');
  check(await page.locator('.thumb').count() === 66, 'gallery lists 66 design states');
  const tokens = await page.evaluate(() => ({ r: T.screen.corner_radius, touch: T.min_touch, hold: I.danger_hold_ms }));
  check(tokens.r === 60 && tokens.touch === 84 && tokens.hold === 600, 'R60, 84 px touch and 600 ms hold tokens');
  await settle(500);
  check((await toastText()).includes('2 updates'), 'launch toast announces 2 updates');
  await shot('01-home');
  await page.locator('#screen .toast-hit').click();
  await settle();
  check(await view() === 'updates', 'tapping the update toast opens Updates');
  await reset();

  // 2. Home list order and rows.
  const labels = await rowLabels('apps');
  check(labels.length === 20, 'home lists 20 apps');
  check(labels[0] === 'Pixel Pet' && labels[1] === 'Weather Station', 'current app first, then recent');
  check(await text('home_title') === 'My apps', 'filter label is My apps');
  check(await text('status_badge') === '↑ 2', 'status strip shows ↑ 2');

  // 3. Browse sheet: open, filter, close by tapping above the sheet and by dragging down.
  await tap('button_filter', 420);
  check(await has('category_favorites'), 'My apps opens the Browse sheet');
  await shot('02-browse');
  await tap('category_favorites', 520);
  check(await text('home_title') === 'Favorites' && (await rows('apps').count()) === 3, 'Favorites filter shows 3 apps');
  await tap('button_filter', 420);
  await drag(240, 30, 240, 30, 1, 120);
  await page.mouse.click((await screenBox()).x + 240 * ((await screenBox()).width / 480), (await screenBox()).y + 50);
  await settle(420);
  check(!(await page.evaluate(() => model.drawer)), 'tapping above the sheet closes it');
  await tap('button_filter', 420);
  await drag(240, 140, 240, 320, 8, 420);
  check(!(await page.evaluate(() => model.drawer)), 'dragging the sheet down closes it');
  await tap('button_filter', 420);
  await tap('category_all', 520);

  // 4. AI key: single press hint, double press quick switch, hold to open.
  await ai(55, 520);
  check((await toastText()).includes('Press AI twice'), 'single AI on Home shows the hint');
  await page.evaluate(() => hideToast());
  await aiDouble();
  check(await has('switch_name'), 'AI ×2 opens quick switch');
  const first = await text('switch_name');
  await ai(55, 200);
  const second = await text('switch_name');
  check(first && second && first !== second, 'single AI in quick switch moves to the next app');
  await shot('03-quick-switch');
  await page.waitForTimeout(4300);
  check(!(await has('switch_name')), 'quick switch closes after 4 s idle');
  await aiDouble();
  await ai(700, 400);
  check(await view() === 'progress', 'holding AI in quick switch opens the app (switching progress)');
  await page.waitForTimeout(3200);
  check(await view() === 'result', 'install ends on the result page');
  await shot('04-result-installed');
  await page.waitForTimeout(4200);
  check(['launching', 'running'].includes(await view()), 'countdown launches the app');
  await reset();

  // 5. Back: AI, Esc and edge swipe that follows the finger.
  await tap('button_device');
  check(await view() === 'device', 'device button opens Device');
  await ai();
  await settle();
  check(await view() === 'home', 'AI goes back immediately');
  await tap('button_device');
  await drag(6, 240, 40, 240, 6, 400);
  check(await view() === 'device', 'short edge drag snaps back');
  await drag(6, 240, 220, 240, 10, 500);
  check(await view() === 'home', 'long edge drag goes back');

  // 6. Detail: two pages, favorites, hold to delete.
  await rows('apps').nth(1).click();
  await settle();
  check(await view() === 'detail' && await text('detail_title') === 'Weather Station', 'row opens detail');
  check(await text('button_primary') === 'Open app', 'local app primary is Open app');
  await shot('05-detail');
  await tap('button_favorite', 200);
  check((await toastText()).includes('Removed from Favorites'), 'star toggles favorite');
  await drag(240, 300, 240, 160, 8, 450);
  check(await page.evaluate(() => model.detail.page) === 2, 'swipe up opens About');
  await drag(240, 200, 240, 360, 8, 450);
  check(await page.evaluate(() => model.detail.page) === 1, 'swipe down returns to page 1');
  await tap('button_more', 420);
  check(await has('button_delete'), 'About this app opens page 2 with delete');
  await shot('06-detail-about');
  await hold('button_delete', 250);
  check(await view() === 'detail', 'short hold does not delete');
  await hold('button_delete', 760);
  check(await view() === 'home' && !(await rowLabels('apps')).includes('Weather Station'), 'full hold deletes and returns Home');
  check((await toastText()).includes('Deleted Weather Station'), 'delete toast');
  await reset();

  // 7. Download by ID: errors, lookup, download & open.
  await tap('button_download');
  await typeKeys('404040');
  check(await text('id_digits') === '404040', 'typed digits show in the ID card');
  await page.keyboard.press('Enter');
  await page.waitForTimeout(1100);
  check(await text('id_status_small') === 'No app with this ID', 'unknown ID error');
  await shot('07-download-error');
  await page.keyboard.press('Backspace');
  check((await text('id_digits')).length === 5 || (await text('id_digits_small')).length === 5, 'backspace removes one digit');
  await page.evaluate(() => { model.dl.digits = ''; render(0); });
  await typeKeys('238114');
  await page.keyboard.press('Enter');
  await page.waitForTimeout(1300);
  check(await view() === 'detail' && await text('button_primary') === 'Download & open', 'store app detail offers Download & open');
  await tap('button_secondary', 500);
  check(await view() === 'progress' && await has('button_cancel'), 'Save shows download progress with Cancel');
  await shot('08-progress');
  await tap('button_cancel', 420);
  check(await view() === 'detail' && (await toastText()).includes('Download cancelled'), 'Cancel returns to detail');
  await tap('button_secondary', 300);
  await page.waitForTimeout(3800);
  check(await view() === 'result' && await text('result_title') !== '', 'save ends on result');
  await tap('button_result_right', 420);
  check(await view() === 'download' || await view() === 'home', 'result Done returns');
  await reset();

  // 8. Offline lookup resumes after connecting (wrong password first).
  await panel('simWifi');
  await tap('button_download');
  await typeKeys('238114');
  await page.keyboard.press('Enter');
  await settle(420);
  check(await view() === 'wifi' && (await text('wifi_detail')).includes('238114'), 'offline lookup goes to Wi‑Fi with the pending task');
  await shot('09-wifi-pending');
  const nets = await rowLabels('networks');
  await rows('networks').nth(nets.indexOf('Maker Lab')).click();
  await settle();
  check(await view() === 'password', 'secured network asks for the password');
  await typeKeys('short');
  await page.keyboard.press('Enter');
  await settle(200);
  check((await text('password_note')).includes('8 or more'), 'short password error');
  await page.evaluate(() => { model.entry.text = ''; render(0); });
  await typeKeys('wrongpass');
  await page.keyboard.press('Enter');
  await page.waitForTimeout(1400);
  check((await text('password_note')).includes('Wrong password'), 'wrong password error');
  await page.evaluate(() => { model.entry.text = ''; render(0); });
  await typeKeys('maker2026');
  await page.keyboard.press('Enter');
  await settle(300);
  check(await view() === 'password' && (await text('password_note')).includes('Connecting'), 'password page shows Connecting');
  await page.waitForTimeout(3000);
  check(await view() === 'detail' && await text('detail_title') === 'Retro Snake', 'lookup resumes after connecting');
  await reset();

  // 9. Background updates.
  await tap('button_device');
  const deviceRows = await page.locator('#screen [data-name^="button_device_"]').count();
  check(deviceRows >= 6, 'Device lists its settings rows');
  await page.evaluate(() => onAction('go:updates'));
  await settle();
  check((await rowLabels('updates')).length === 2, 'Updates lists 2 apps');
  await tap('button_update_all', 300);
  check((await text('updates_summary')).includes('in the background'), 'Update all runs in the background');
  await shot('10-updates-running');
  await ai(); await settle(); await ai(); await settle(500);
  check(await view() === 'home' && (await text('status_badge')).startsWith('↓'), 'Home strip shows ↓ k/n');
  await page.waitForFunction(() => !model.bg, null, { timeout: 12000 });
  await settle(200);
  const badge = await text('status_badge'), finished = await toastText();
  check(badge === '' && finished.includes('Apps updated'), `updates finish with a toast (badge "${badge}", toast "${finished}")`);
  await reset();

  // 10. Storage full → Free up space → storage rows.
  await panel('simStorage');
  await tap('button_download');
  await typeKeys('507219');
  await page.keyboard.press('Enter');
  await page.waitForTimeout(1200);
  check(await text('button_primary') === 'Free up space', 'no space detail offers Free up space');
  await tap('button_primary');
  check(await view() === 'storage' && (await rows('storage').count()) === 20, 'Free up space opens App storage');
  await shot('11-storage');
  await rows('storage').nth(0).click();
  await settle();
  check(await view() === 'detail' && await page.evaluate(() => model.detail.page) === 2, 'storage row opens About with delete');
  await reset();

  // 11. Mosaico AI: hold to turn off, offline claim resumes.
  await page.evaluate(() => { stack.push({ view: 'token', params: {} }); render(1); });
  await settle();
  await hold('button_turn_off', 760);
  check(await page.evaluate(() => model.tokenKind) === 'none', 'hold turns Mosaico AI off');
  await panel('simWifi');
  await tap('button_claim');
  check(await view() === 'wifi', 'offline Turn on goes to Wi‑Fi');
  const nets2 = await rowLabels('networks');
  await rows('networks').nth(nets2.indexOf('Espressif-Guest')).click();
  await page.waitForTimeout(1800);
  check(await page.evaluate(() => model.tokenKind) === 'mosaico' && await view() === 'token', 'claim resumes after connecting');
  await reset();

  // 12. Low battery blocks switching; USB deploy and return to Vibe Mode.
  await panel('simLowBat');
  await rows('apps').nth(1).click(); await settle();
  await tap('button_primary', 420);
  check(await view() === 'result' && await page.evaluate(() => model.result.kind) === 'battery', 'low battery blocks switching');
  await reset();
  await panel('simDeploy', 300);
  check(await view() === 'progress', 'USB deploy shows progress');
  await page.waitForTimeout(8800);
  check(await view() === 'running', 'deployed app runs');
  await blur();
  await page.keyboard.down('ArrowUp');
  await page.locator('#powerKey').dblclick();
  await page.waitForTimeout(1200);
  await page.keyboard.up('ArrowUp');
  await settle();
  check(await view() === 'home', 'AI + double power returns to Vibe Mode');
  await reset();

  // 13. Guide.
  await panel('simGuide', 1300);
  check(await view() === 'guide', 'first boot shows the guide');
  for (let i = 0; i < 4; i++) await tap('button_guide_next', 380).catch(() => {});
  check(await page.evaluate(() => cur().params.step) === 5, 'guide reaches step 5');
  await shot('12-guide-5');
  await tap('button_guide_wifi', 420);
  check(await view() === 'wifi', 'Connect on step 5 opens Wi‑Fi');

  check(errors.length === 0, `no script errors${errors.length ? ': ' + errors.join(' | ') : ''}`);
  console.log(`\n${pass} passed, ${fail} failed`);
  await browser.close();
  process.exit(fail ? 1 : 0);
})();
