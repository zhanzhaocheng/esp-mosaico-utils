// Playwright smoke coverage for the Vibe Mode v11 single-file prototype.
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
  // Record haptics: navigator.vibrate is stubbed so touch-down timing can be checked.
  await page.addInitScript(() => { window.__vib = []; navigator.vibrate = (p) => { window.__vib.push(p); return true; }; });
  await page.goto(`file://${pageFile}`);
  await page.waitForTimeout(400);

  // The live page is the last .page layer; a leaving one is removed after its slide.
  const loc = (name) => page.locator(`#screen [data-name="${name}"]`).last();
  const has = async (name) => (await page.locator(`#screen [data-name="${name}"]`).count()) > 0;
  const text = async (name) => ((await loc(name).textContent({ timeout: 1500 }).catch(() => null)) || '').trim();
  const view = () => page.evaluate(() => cur().view);
  const mdl = (fn) => page.evaluate(fn);
  const settle = (ms = 340) => page.waitForTimeout(ms);
  const tap = async (name, wait = 340) => { await loc(name).click(); await settle(wait); };
  const panel = async (id, wait = 240) => { await page.locator(`#${id}`).click(); await settle(wait); };
  const blur = () => page.evaluate(() => document.activeElement?.blur());
  const ai = async (ms = 55, wait = 420) => {
    await blur();
    await page.keyboard.down('ArrowUp');
    await page.waitForTimeout(ms);
    await page.keyboard.up('ArrowUp');
    await page.waitForTimeout(wait);
  };
  const reset = async () => { await panel('simReset', 450); };
  const rows = (kind) => page.locator(`#screen .row-hit[data-row^="${kind}:"]`);
  const rowLabels = async (kind) => rows(kind).evaluateAll((els) => els.map((e) => e.getAttribute('aria-label')));
  const center = async (name) => {
    const box = await loc(name).boundingBox();
    return { x: box.x + box.width / 2, y: box.y + box.height / 2 };
  };
  const hold = async (name, ms = 760) => {
    const c = await center(name);
    await page.mouse.move(c.x, c.y);
    await page.mouse.down();
    await page.waitForTimeout(ms);
    await page.mouse.up();
    await settle(420);
  };
  const screenBox = async () => page.locator('#screen').boundingBox();
  const drag = async (x0, y0, x1, y1, steps = 8, wait = 480) => {
    const b = await screenBox(), k = b.width / 480;
    await page.mouse.move(b.x + x0 * k, b.y + y0 * k);
    await page.mouse.down();
    for (let i = 1; i <= steps; i++) await page.mouse.move(b.x + (x0 + (x1 - x0) * i / steps) * k, b.y + (y0 + (y1 - y0) * i / steps) * k);
    await page.mouse.up();
    await settle(wait);
  };
  // Swipe a list row horizontally (negative dx = left), in screen pixels.
  const swipeRow = async (kind, i, dx = -170) => {
    const b = await rows(kind).nth(i).boundingBox(), k = (await screenBox()).width / 480;
    const x0 = b.x + b.width * 0.7, y = b.y + b.height / 2;
    await page.mouse.move(x0, y);
    await page.mouse.down();
    for (let s = 1; s <= 8; s++) await page.mouse.move(x0 + dx * k * s / 8, y);
    await page.mouse.up();
    await settle(360);
  };
  const openDelete = () => page.locator('#screen .swipe-row.open [data-name="button_swipe_delete"]');
  const slots = async () => (await Promise.all([0, 1, 2, 3, 4, 5].map((i) => text(`id_slot_${i}`)))).join('');
  const noStatusBar = () => mdl(() => !pageLayer.querySelector('[data-name="nav_badge"]'));
  const typeKeys = async (s) => { await blur(); for (const ch of s) await page.keyboard.press(ch); };
  const shot = async (name) => { if (out) await page.locator('#screen').screenshot({ path: path.join(out, `${name}.png`) }); };
  const toManage = async () => { await tap('button_manage'); };
  const toDownload = async () => { await toManage(); await tap('button_add_download'); };
  const openTile = async (id, wait = 400) => { await tap(`button_idea_${id}`, 300); await tap('button_confirm_open', wait); };
  const vib = () => mdl(() => window.__vib.length);
  const bg = (name) => loc(name).evaluate((el) => getComputedStyle(el).backgroundColor);
  // Images on the live page that failed to load (empty src or no pixels).
  const brokenImgs = () => page.evaluate(() => [...pageLayer.querySelectorAll('img')].filter((i) => !i.getAttribute('src') || !i.naturalWidth).length);
  const kbGo = () => page.locator('#screen .kb-key[data-key="kb:go"]').last().getAttribute('data-ready');

  // 1. Load, tokens, gallery.
  check(errors.length === 0, 'loads without script errors');
  const stateCount = await mdl(() => LAYOUT.states.length);
  check(await page.locator('.thumb').count() === stateCount && stateCount > 0, `gallery lists all ${stateCount} design states`);
  const tokens = await mdl(() => ({ r: T.screen.corner_radius, touch: T.min_touch, hold: I.danger_hold_ms, undo: I.undo_ms, schema: LAYOUT.schema }));
  check(tokens.r === 60 && tokens.touch === 84 && tokens.hold === 3000 && tokens.undo === 4000, 'R60, 84 px touch, 3 s hold and 4 s Undo tokens');
  check(tokens.schema === 'vibe-mode-design/11', 'layout schema is vibe-mode-design/11');

  // 2. Home: quiet status bar, pager dots, hero animation, first-use hint.
  check(await view() === 'home' && await text('nav_badge') === '', 'home has no update badge in the status bar');
  check(await has('pager_hint') && (await loc('pager_hint').evaluate((el) => getComputedStyle(el).animationName)) === 'nudge', 'first use shows the moving swipe hint');
  check(await page.locator('#screen [data-name^="pager_hit_"]').count() === 5, 'pager has 5 tappable dots');
  const f1 = await loc('home_hero').getAttribute('src');
  await page.waitForTimeout(450);
  const f2 = await loc('home_hero').getAttribute('src');
  check(f1 && f2 && f1 !== f2, 'home hero animates');
  await shot('01-home');

  // 3. Swipe between home and the Ideas pages: only the content moves; dots are tappable.
  {
    const b = await screenBox(), k = b.width / 480;
    const nav0 = (await loc('nav_product').boundingBox()).x, dot0 = (await loc('pager_dot_0').boundingBox()).x;
    const title0 = (await loc('home_title_a').boundingBox()).x;
    await page.mouse.move(b.x + 400 * k, b.y + 130 * k);
    await page.mouse.down();
    for (let i = 1; i <= 6; i++) await page.mouse.move(b.x + (400 - 25 * i) * k, b.y + 130 * k);
    const nav1 = (await loc('nav_product').boundingBox()).x, dot1 = (await loc('pager_dot_0').boundingBox()).x;
    const title1 = (await page.locator('#screen .pager-content [data-name="home_title_a"]').first().boundingBox()).x;
    check(nav1 === nav0 && dot1 === dot0 && title1 < title0 - 50, 'while dragging, the status bar and dots stay put and only the content moves');
    for (let i = 7; i <= 12; i++) await page.mouse.move(b.x + (400 - 25 * i) * k, b.y + 130 * k);
    await page.mouse.up();
    await settle(520);
  }
  check(await view() === 'ideas' && await mdl(() => cur().params.page) === 1, 'swipe left on Home opens Ideas page 1');
  check(await has('button_idea_100001') && (await text('nav_badge')) === 'Ideas 1/4', 'the status bar names the page');
  await page.waitForTimeout(2100);
  check((await text('nav_badge')) === '', 'the page name clears after a moment');
  check(await has('idea_ring_100001') && await has('idea_badge_100006'), 'current Idea has a ring and updatable Ideas a badge');
  check(await brokenImgs() === 0 && await loc('idea_icon_100001').getAttribute('src') === await mdl(() => ASSETS['assets/ideas/pet-talk-108.png']), 'Idea tiles use the Mosaico launcher icons');
  await shot('02-ideas-1');
  await drag(100, 130, 400, 130, 8, 520);
  check(await view() === 'home' && await text('nav_badge') === 'Home' && !(await has('pager_hint')), 'swipe right returns Home; the hint is gone for good');
  await drag(120, 130, 150, 130, 6, 480);
  check(await view() === 'home', 'a short swipe snaps back to Home');
  {
    // Regressions: releasing outside the screen, and a second swipe while the first still slides.
    const sb = await screenBox(), k = sb.width / 480;
    const contents = () => mdl(() => pageLayer.querySelectorAll(':scope > .pager-content').length);
    await page.mouse.move(sb.x + 400 * k, sb.y + 200 * k);
    await page.mouse.down();
    for (let i = 1; i <= 10; i++) await page.mouse.move(sb.x + (400 - 50 * i) * k, sb.y + 200 * k);
    await page.mouse.up();
    await settle(500);
    check(await contents() === 1 && await mdl(() => !gst && model.page === 1), 'releasing a swipe outside the screen still finishes it cleanly');
    for (let n = 0; n < 2; n++) {
      await page.mouse.move(sb.x + 420 * k, sb.y + 200 * k);
      await page.mouse.down();
      for (let i = 1; i <= 5; i++) await page.mouse.move(sb.x + (420 - 60 * i) * k, sb.y + 200 * k);
      await page.mouse.up();
      await settle(60);
    }
    await settle(500);
    check(await contents() === 1 && await mdl(() => model.page) === 3, 'two quick swipes leave exactly one page on screen');
    await tap('pager_hit_0', 520);
  }
  await tap('pager_hit_2', 520);
  check(await view() === 'ideas' && await mdl(() => cur().params.page) === 2, 'tapping the third dot opens Ideas page 2');
  await tap('pager_hit_4', 520);
  check(await has('button_add_idea') && await has('idea_add_visual') && await mdl(() => cur().params.page) === 4, 'last Ideas page ends with the big + cell');
  await tap('button_add_idea', 400);
  check(await view() === 'download' && await mdl(() => stack.map((e) => e.view).join()) === 'ideas,manage,download', '+ opens Download inside Manage');
  await ai();
  check(await view() === 'manage', 'Back from there goes to Manage');
  await reset();

  // 4. AI key and sub-page chrome.
  await tap('pager_hit_1', 520);
  await ai();
  check(await view() === 'home' && await mdl(() => model.page) === 0, 'AI on an Ideas page goes Home');
  await blur();
  await page.keyboard.down('ArrowUp');
  await settle(60);
  check(await page.locator('#keyFb.down').count() === 1, 'pressing AI lights the bar under the key at once');
  await page.keyboard.up('ArrowUp');
  await settle(150);
  check((await page.locator('#keyFb .chip').textContent()) === 'Lock' && await mdl(() => !!model.sleeping), 'AI on Home turns the screen off; the chip says Lock');
  check(await has('sleep_title_a') && await mdl(() => !model.wifi.connected), 'the screen-off view shows Make Ideas Run and Wi-Fi is off');
  await shot('03-sleep');
  await tap('button_wake', 300);
  check(await mdl(() => !model.sleeping) && await view() === 'home', 'a tap wakes it');
  await page.waitForTimeout(1400);
  check(await mdl(() => model.wifi.connected), 'Wi-Fi reconnects after waking');
  await tap('button_settings');
  check(await view() === 'settings' && await text('settings_wifi') === 'Studio-5G', 'Settings opens and shows the Wi-Fi name');
  check(await noStatusBar() && await has('button_back_settings'), 'sub-pages have no status bar, just Back and the title');
  await shot('03-settings');
  await ai();
  check(await view() === 'home', 'AI on Settings goes back');
  await tap('button_settings');
  await drag(6, 240, 40, 240, 6, 400);
  check(await view() === 'settings', 'short edge drag snaps back');
  await drag(6, 240, 220, 240, 10, 500);
  check(await view() === 'home', 'long edge drag goes back');

  // 5. Tapping an Idea asks first; then launching and running.
  await tap('pager_hit_1', 520);
  await tap('button_idea_100001', 300);
  check(await view() === 'ideas' && await text('confirm_title') === 'Open Pet Talk?' && await text('confirm_key_ai_chip') === 'Hold AI' && await text('confirm_key_power_chip') === 'Press twice', 'tapping an Idea opens a confirm dialog with arrows at the AI and power keys');
  {
    const sb = await screenBox(), k = sb.width / 480;
    const up = await loc('confirm_key_ai_arrow').boundingBox(), down = await loc('confirm_key_power_arrow').boundingBox();
    check((up.y - sb.y) / k < 20 && (down.y - sb.y) / k > 440 && Math.abs((up.x - sb.x) / k + 12 - 372) < 2, 'the arrows sit on the top and bottom edges right under the keys');
  }
  await shot('03-confirm');
  await tap('button_confirm_cancel', 300);
  check(!(await page.locator('#screen .modal-layer.show').count()), 'Cancel closes the dialog');
  await tap('button_idea_100001', 300);
  await ai();
  check(!(await page.locator('#screen .modal-layer.show').count()) && await view() === 'ideas', 'AI closes the dialog too');
  await openTile('100001', 300);
  check(await view() === 'launching' && (await text('launch_title')).includes('Pet Talk'), 'Open goes to Launching');
  await page.waitForTimeout(1700);
  check(await view() === 'running', 'current Idea ends in Running');
  await blur();
  await page.keyboard.down('ArrowUp');
  await page.locator('#powerKey').dblclick();
  await page.waitForTimeout(1300);
  await page.keyboard.up('ArrowUp');
  await settle();
  check(await view() === 'home', 'AI + double power returns to Vibe Mode');
  await reset();

  // 6. Open another Idea: "Don't show again", Cancel window, then write and launch.
  await tap('pager_hit_1', 520);
  await tap('button_idea_100002', 300);
  await tap('button_confirm_skip', 200);
  check(await has('confirm_skip_check'), "Don't show this again can be ticked");
  await tap('button_confirm_open', 400);
  check(await view() === 'progress' && await has('button_cancel') && await noStatusBar(), 'another Idea shows Switching with Cancel and no status bar');
  await tap('button_cancel', 420);
  check(await view() === 'ideas' && await mdl(() => model.current) === '100001' && (await text('nav_badge')) === 'Cancelled', 'Cancel returns to the Ideas page and flashes Cancelled in the status bar');
  await tap('button_idea_100002', 1900);
  check(await view() === 'progress' && !(await has('button_cancel')), 'with the tick, the next tap skips the dialog; Cancel disappears once writing starts');
  await page.waitForTimeout(2200);
  check(await mdl(() => model.current) === '100002', 'switch sets the current Idea');
  await reset();

  // 7. Manage: order, scrollbar, the header update button.
  await toManage();
  let labels = await rowLabels('manage');
  check(await view() === 'manage' && labels.length === 20, 'Manage lists 20 Ideas');
  check(labels[0] === 'Pet Talk' && labels[1] === 'Agenda' && labels[2] === 'Weather', 'current Idea first, then the ones with updates');
  check((await text('manage_summary')).startsWith('20 Ideas'), 'Manage shows the count and storage use');
  check(await text('button_update_all_badge') === '2' && !(await has('update_all_sub')), 'updates are a header button with a count, not a row');
  check(await mdl(() => named(STATES_BY.en.manage.objects, 'button_update_all_icon').image.includes('upgrade')), 'the update button uses the upward upgrade icon');
  check(await loc('manage_scroll_thumb').isVisible(), 'the list shows a scrollbar');
  const t0 = await loc('manage_scroll_thumb').evaluate((el) => el.offsetTop);
  await page.evaluate(() => { const l = document.querySelector('#screen [data-list="manage"]'); l.scrollTop = 600; l.dispatchEvent(new Event('scroll')); });
  await settle(100);
  check(await loc('manage_scroll_thumb').evaluate((el) => el.offsetTop) > t0, 'the scrollbar thumb follows the list');
  await page.evaluate(() => { const l = document.querySelector('#screen [data-list="manage"]'); l.scrollTop = 0; l.dispatchEvent(new Event('scroll')); });
  await shot('04-manage');
  await tap('button_update_all', 360);
  check(await has('button_update_all_spinner'), 'the update button spins while updating');
  check((await rowLabels('manage'))[1] === 'Agenda', 'updating rows stay in place');
  await shot('05-manage-updating');
  await page.waitForFunction(() => !model.bg, null, { timeout: 12000 });
  await settle(200);
  check(await text('toast_text') === 'Updated' && !(await has('button_update_all')), 'updates finish with an Updated toast and the button goes away');
  await ai();
  await tap('pager_hit_1', 520);
  check(!(await has('idea_badge_100006')), 'update badges are gone from the Ideas page');
  await reset();

  // 8. Swipe to delete, Undo; the current Idea cannot be swiped away.
  await toManage();
  await swipeRow('manage', 3);
  check(await page.locator('#screen .swipe-row.open').count() === 1, 'swiping a row left reveals Delete');
  await shot('06-manage-swipe');
  await openDelete().click();
  await settle(360);
  labels = await rowLabels('manage');
  check(labels.length === 19 && !labels.includes('Clock'), 'Delete removes the Idea at once');
  check(await text('toast_text') === 'Deleted Clock' && await has('button_undo'), 'the toast offers Undo');
  await shot('07-manage-undo');
  await tap('button_undo', 360);
  labels = await rowLabels('manage');
  check(labels.length === 20 && labels[3] === 'Clock', 'Undo puts it back in the same place');
  await swipeRow('manage', 0);
  check(await page.locator('#screen .swipe-row.open').count() === 0 && await text('toast_text') === "Can't delete the current Idea", 'the current Idea bounces back with a reason');
  await swipeRow('manage', 1);
  await rows('manage').nth(2).click();
  await settle();
  check(await view() === 'manage' && await page.locator('#screen .swipe-row.open').count() === 0, 'tapping elsewhere just closes the open row');
  await reset();

  // 9. Idea info: Open + Delete side by side, QR page with Back.
  await toManage();
  await rows('manage').nth(3).click();
  await settle();
  check(await view() === 'idea_info' && await text('info_title') === 'Clock', 'Manage row opens Idea info');
  check(await has('button_open') && await has('button_delete') && !(await has('button_rename')), 'Open and Delete sit side by side; no Rename');
  await tap('button_qr_idea', 420);
  check(await view() === 'qr' && await has('qr_code') && (await text('qr_desc')).length > 20 && await has('button_back_qr'), 'QR page explains the code and has Back');
  check(await loc('qr_code').evaluate((el) => el.getBoundingClientRect().width) < 260, 'the QR code is a modest size');
  await shot('08-qr');
  await tap('button_back_qr', 420);
  check(await view() === 'idea_info', 'Back leaves the QR page');
  await tap('button_delete', 300);
  check(await view() === 'idea_info' && await text('toast_text') === 'Hold for 3 s to delete', 'a tap on Delete explains the 3 s hold');
  {
    const c = await center('button_delete'), openW = (await loc('button_open').boundingBox()).width;
    await page.mouse.move(c.x, c.y);
    await page.mouse.down();
    await page.waitForTimeout(700);
    const shrunk = (await loc('button_open').boundingBox()).width < openW * 0.6;
    check(shrunk && await has('delete_popup_title') && (await text('button_delete')).startsWith('Keep holding'), 'holding: Open shrinks, Delete widens, a popup counts down');
    await shot('09-delete-hold');
    await page.mouse.up();
    await settle(400);
    check(await view() === 'idea_info' && await text('toast_text') === 'Not deleted' && !(await has('delete_popup_title')), 'letting go early cancels');
  }
  await hold('button_delete', 3300);
  check(await view() === 'manage' && (await rowLabels('manage')).length === 19 && await text('toast_text') === 'Deleted Clock', 'a full 3 s hold deletes and returns to Manage');
  await tap('button_undo', 360);
  check((await rowLabels('manage')).length === 20, 'Undo restores it');
  await rows('manage').nth(0).click();
  await settle();
  await tap('button_delete', 360);
  check(await view() === 'idea_info' && await text('toast_text') === 'Open another Idea first', 'the current Idea\'s Delete is disabled and says why');
  await reset();

  // 10. Download by ID: slots, errors, lookup, download, cancel, save.
  await toDownload();
  check(await view() === 'download' && await has('key_5') && await noStatusBar(), 'Download shows the keypad, no status bar');
  {
    const c = await center('key_5'), n0 = await vib();
    await page.mouse.move(c.x, c.y);
    await page.mouse.down();
    await settle(80);
    const grown = await loc('key_5_visual').evaluate((el) => el.classList.contains('pressed') && el.dataset.grow === '1');
    check(grown && await vib() === n0 + 1, 'a key grows and ticks on touch-down, before release');
    await page.mouse.up();
    await settle(120);
    await mdl(() => { model.dl.digits = ''; render(0); });
  }
  await typeKeys('4040');
  check(await bg('key_go_visual') !== 'rgb(255, 76, 1)', 'Go stays grey until six digits');
  await typeKeys('40');
  check(await bg('key_go_visual') === 'rgb(255, 76, 1)', 'Go turns orange with six digits');
  await mdl(() => { model.dl.digits = ''; render(0); });
  await typeKeys('404040');
  check(await slots() === '404040', 'digits fill the six slots');
  await page.keyboard.press('Enter');
  await page.waitForTimeout(1100);
  check(await text('id_status') === 'No Idea with this ID', 'unknown ID error');
  await shot('09-download-error');
  await page.keyboard.press('Backspace');
  check(await slots() === '40404', 'backspace removes one digit');
  await mdl(() => { model.dl.digits = ''; render(0); });
  await tap('key_2', 60); await tap('key_3', 60); await tap('key_8', 60);
  check(await slots() === '238', 'tapping keys fills the slots');
  await typeKeys('114');
  await tap('key_go', 1300);
  check(await view() === 'idea_info' && await text('info_title') === 'Rolling Maze' && await has('button_download'), 'lookup opens the store Idea with Download');
  await tap('button_download', 400);
  check(await view() === 'progress' && await has('button_cancel'), 'Download shows progress with Cancel');
  await tap('button_cancel', 420);
  check(await view() === 'idea_info' && await text('toast_text') === 'Cancelled', 'Cancel returns to Idea info with a toast');
  await tap('button_download', 400);
  await page.waitForTimeout(3900);
  check(await view() === 'result' && await text('result_title') === 'Idea saved', 'download ends on Idea saved');
  check(await mdl(() => window.__vib.some((p) => JSON.stringify(p) === JSON.stringify(T.haptics.success))), 'finishing a download gives the success haptic');
  await tap('button_result_left', 420);
  check(await view() === 'idea_info' && await has('button_open') && await mdl(() => model.ideas.length) === 21, 'Done returns to Idea info with the Idea installed');
  await ai(); await ai(); await ai();
  check(await view() === 'home', 'AI backs out of the stack to Home');
  await tap('pager_hit_4', 520);
  check(await has('idea_icon_238114'), 'the new Idea appears on the last Ideas page');
  await reset();

  // 11. Shared info: no Wi-Fi row, help, add, edit key and value, delete with Undo, swipe.
  await mdl(() => localStorage.removeItem('vibe-shared-nvs'));
  await tap('button_settings');
  check(await text('settings_shared') === '3 entries', 'Settings shows 3 shared entries');
  await tap('button_shared');
  labels = await rowLabels('shared');
  check(labels.join(',') === 'city,api_key,units' && !(await has('button_shared_wifi')), 'Shared info lists only the custom entries');
  check(await brokenImgs() === 0 && await page.locator('#screen [data-list="shared"] [data-name="shared_icon"]').count() === 3, 'every Shared row shows its key / lock icon');
  await shot('10-shared');
  await tap('button_shared_help', 420);
  check(await view() === 'shared_help' && (await text('shared_help_body')).startsWith('Shared info is'), '? explains what shared info is');
  await ai();
  await tap('button_add_entry', 420);
  check(await view() === 'shared_add' && await has('shared_add_key_keyboard') && await kbGo() === '0', 'Add opens the key step with GO grey');
  await typeKeys('C ');
  check((await text('shared_add_key_display')) === 'c' && (await text('shared_add_key_note')).startsWith('Use a–z'), 'keys are lower-cased and only take a–z, 0–9 and _');
  await mdl(() => { model.entry.text = ''; model.entry.error = ''; render(0); });
  await typeKeys('color');
  check(await kbGo() === '1', 'GO turns orange once a key is typed');
  await page.keyboard.press('Enter');
  await settle(420);
  check(await has('shared_add_value_keyboard') && (await text('shared_add_value_note')).includes('color'), 'Go moves to the value step');
  await typeKeys('blue');
  await page.keyboard.press('Enter');
  await settle(420);
  check(await view() === 'shared' && (await rowLabels('shared')).includes('color') && await text('toast_text') === 'Saved', 'saving returns to the list with a Saved toast');
  const stored = await mdl(() => JSON.parse(localStorage.getItem('vibe-shared-nvs')));
  check(stored.some((e) => e.key === 'color' && e.value === 'blue'), 'the entry is written to localStorage');
  check((await page.locator('#nvsDump').textContent()).includes('shared/color = "blue"'), 'the NVS panel shows the entry');
  await rows('shared').nth((await rowLabels('shared')).indexOf('color')).click();
  await settle(420);
  check(await view() === 'shared_entry' && await text('entry_key') === 'color' && await text('entry_value') === 'blue', 'row opens the entry with Key and Value');
  await tap('button_edit_value', 420);
  await page.keyboard.press('Backspace');
  await typeKeys('e');
  await page.keyboard.press('Enter');
  await settle(420);
  check(await view() === 'shared_entry' && await text('entry_value') === 'blue', 'Edit value saves and returns to the entry');
  await tap('button_edit_key', 420);
  check(await text('shared_add_key_display') === 'color', 'Rename key starts from the current key');
  await typeKeys('2');
  await page.keyboard.press('Enter');
  await settle(420);
  check(await view() === 'shared_entry' && await text('shared_entry_title') === 'color2' && await text('entry_key') === 'color2', 'the key is renamed');
  check((await page.locator('#nvsDump').textContent()).includes('shared/color2 = "blue"'), 'the NVS panel shows the new key');
  await tap('button_delete_entry', 420);
  check(await view() === 'shared' && !(await rowLabels('shared')).includes('color2') && await text('toast_text') === 'Deleted color2', 'Delete entry closes the page with Undo');
  await tap('button_undo', 360);
  check((await rowLabels('shared')).includes('color2'), 'Undo restores the entry');
  await swipeRow('shared', (await rowLabels('shared')).indexOf('color2'));
  await openDelete().click();
  await settle(360);
  check(!(await rowLabels('shared')).includes('color2') && !(await page.locator('#nvsDump').textContent()).includes('color2'), 'swipe Delete removes it from NVS');
  await reset();

  // 12. Offline: Home offers a red Wi-Fi alert; Download shows the offline page; a typed ID resumes after connecting.
  await panel('simWifi');
  check(await has('home_wifi_alert') && !(await has('home_intro')) && await loc('home_wifi_alert_text').evaluate((el) => getComputedStyle(el.querySelector('span')).color) === 'rgb(229, 72, 77)', 'offline Home shows a red Wi-Fi alert instead of the intro');
  await tap('button_home_wifi', 400);
  check(await view() === 'wifi', 'tapping the alert opens Wi-Fi');
  await ai();
  await toDownload();
  check(await has('download_offline_title') && await has('button_connect_wifi'), 'offline Download shows Wi-Fi is off');
  await reset();
  await toDownload();
  await typeKeys('238114');
  await panel('simWifi', 300);
  await blur();
  await page.keyboard.press('Enter');
  await settle(420);
  check(await view() === 'wifi' && (await text('wifi_detail')).includes('238114'), 'offline lookup goes to Wi-Fi with the pending task');
  await shot('11-wifi-pending');
  check(await brokenImgs() === 0 && await page.locator('#screen [data-list="networks"] [data-name="networks_icon"]').count() > 0, 'Wi-Fi network rows show their signal icons');
  const nets = await rowLabels('networks');
  await rows('networks').nth(nets.indexOf('Maker Lab')).click();
  await settle();
  check(await view() === 'password', 'a secured network asks for the password');
  await typeKeys('short');
  check(await kbGo() === '0', 'password GO stays grey under 8 characters');
  {
    const g = await page.locator('#screen .kb-key[data-key="kb:go"]').last().boundingBox(), n0 = await vib();
    await page.mouse.move(g.x + g.width / 2, g.y + g.height / 2);
    await page.mouse.down();
    const pattern = await mdl(() => window.__vib[window.__vib.length - 1]);
    check(await vib() === n0 + 1 && pattern.length === 1 && pattern[0] > 8, 'pressing a grey GO gives the softer reject buzz');
    await page.mouse.up();
    await settle(200);
  }
  check((await text('password_note')).includes('8 or more'), 'short password error');
  await mdl(() => { model.entry.text = ''; model.entry.error = ''; render(0); });
  await typeKeys('wrongpass');
  await page.keyboard.press('Enter');
  await page.waitForTimeout(1700);
  check((await text('password_note')).includes('Wrong password') && (await text('password_display')) === 'Type the password', 'wrong password clears the input and shows an error');
  await typeKeys('maker2026');
  check(await kbGo() === '1', 'password GO turns orange at 8 characters');
  await page.keyboard.press('Enter');
  await settle(300);
  check(await view() === 'password' && (await text('password_note')).includes('Connecting'), 'password page shows Connecting');
  await page.waitForTimeout(3300);
  check(await view() === 'idea_info' && await text('info_title') === 'Rolling Maze', 'lookup resumes after connecting');
  await reset();

  // 13. Low battery blocks switching.
  await panel('simLowBat');
  await tap('pager_hit_1', 520);
  await openTile('100002', 420);
  check(await view() === 'result' && await text('result_title') === 'Battery low', 'low battery blocks switching');
  await tap('button_result_right', 420);
  check(await view() === 'ideas', 'OK returns to the Ideas page');
  await reset();

  // 14. Settings: Help topic with QR, About, Develop, Wi-Fi forget.
  await tap('button_settings');
  await tap('button_help');
  await tap('button_help_ids', 420);
  check(await view() === 'help_topic' && await text('help_topic_title') === 'Idea IDs & sharing', 'Help topic opens');
  await tap('button_help_qr', 420);
  check(await view() === 'qr' && await text('qr_title') === 'Idea IDs & sharing' && await has('qr_url'), 'Full guide on your phone opens the QR page');
  await ai(); await ai(); await ai();
  await tap('button_about', 420);
  check(await view() === 'about' && (await text('about_version')) === 'v1.2' && (await text('about_storage')).startsWith('32.8'), 'About shows version and storage');
  await ai(); await ai();
  check(await view() === 'home', 'AI backs out to Home');
  await tap('button_develop');
  check(await view() === 'develop' && (await text('develop_status')).includes('Agent ready') && await brokenImgs() === 0, 'Develop shows USB and agent ready, all icons loaded');
  await panel('simUsb');
  check((await text('develop_status')).includes('Plug in'), 'Develop reflects USB unplugged');
  await ai();
  check(await loc('nav_usb').getAttribute('src') === await mdl(() => ASSETS['assets/icons/usb_off-20-grey.png']), 'unplugged USB shows a slashed icon like Wi-Fi off');
  await tap('button_develop');
  await tap('button_vibe_guide', 420);
  check(await view() === 'qr' && await text('qr_title') === 'Vibe-coding guide', 'Develop links to the guide QR page');
  await reset();
  await tap('button_settings');
  await tap('button_wifi');
  await tap('button_wifi_current', 420);
  await hold('button_forget', 1200);
  check(await view() === 'wifi_network', 'a 1 s hold does not forget the network');
  await hold('button_forget', 3300);
  check(await view() === 'wifi' && await mdl(() => !model.wifi.connected), 'a full hold forgets the network');
  await reset();

  // 15. Screen off by timeout, wake by IMU; Display settings.
  await panel('simIdle', 300);
  check(await mdl(() => !!model.sleeping), 'the idle timeout turns the screen off');
  await panel('simImu', 300);
  check(await mdl(() => !model.sleeping), 'IMU motion wakes it');
  await page.waitForTimeout(1400);
  await tap('button_settings');
  check((await text('settings_display')) === 'Screen off after 3 min' && await loc('settings_scroll_thumb').isVisible(), 'Settings scrolls and shows the screen-off time');
  await tap('button_display');
  check(await view() === 'display' && await bg('button_timeout_180') === 'rgb(242, 242, 242)', 'Display shows 3 min selected');
  await shot('20-display');
  await tap('button_timeout_600', 300);
  check(await mdl(() => model.screenOff) === 600 && await text('toast_text') === 'Screen off after 10 min', 'picking 10 min saves it');
  await tap('button_timeout_0', 300);
  await panel('simIdle', 300);
  check(await mdl(() => !model.sleeping), 'Never keeps the screen on');
  await tap('button_rotate', 300);
  check(await mdl(() => !model.autoRotate) && (await text('display_rotate_sub')) === 'Stays in this orientation', 'Auto-rotate switches off');
  await reset();

  // 16. IMU rotation: the device turns, the UI stays upright; it waits on keyboard pages.
  await page.locator('#rotBtns [data-rot="90"]').click();
  await settle(500);
  let rot = await mdl(() => [document.getElementById('deviceRot').style.transform, screen.style.transform, keyFb.style.getPropertyValue('--chip-rot')]);
  check(rot[0] === 'rotate(90deg)' && rot[1] === 'rotate(-90deg)' && rot[2] === 'rotate(-90deg)', 'turning the device 90° keeps the UI and the AI chip upright');
  await tap('pager_hit_1', 520);
  await tap('button_idea_100002', 300);
  {
    const sb = await screenBox(), k = sb.width / 480, up = await loc('confirm_key_ai_arrow').boundingBox();
    check((up.x - sb.x) / k > 440 && !(await has('confirm_key_ai_chip')), 'rotated: the AI arrow moves to the right edge where the key now is');
  }
  await tap('button_confirm_cancel', 300);
  await ai();
  await shot('21-rotated');
  await tap('button_settings');
  check(await view() === 'settings', 'taps still land correctly when rotated');
  await tap('button_shared');
  await tap('button_add_entry', 420);
  await page.locator('#rotBtns [data-rot="180"]').click();
  await settle(300);
  check(await mdl(() => screen.style.transform) === 'rotate(-90deg)', 'on a keyboard page the UI waits');
  await ai();
  check(await mdl(() => screen.style.transform) === 'rotate(-180deg)', 'leaving the keyboard applies the rotation');
  await reset();
  check(await mdl(() => screen.style.transform) === 'rotate(0deg)', 'reset turns the device upright');

  // 17. Boot key: tip with QR; Boot + power twice → update mode; one press restarts.
  await blur();
  await page.keyboard.down('ArrowDown');
  await settle(800);
  check(await view() === 'boot_tip' && await has('boot_tip_qr') && (await text('boot_tip_body')).startsWith('Only needed'), 'holding Boot explains it is only for updating Vibe Mode, with a QR code');
  await shot('22-boot-tip');
  await page.keyboard.up('ArrowDown');
  await tap('button_boot_tip_ok', 400);
  check(await view() === 'home', 'Got it closes the tip');
  await page.keyboard.down('ArrowDown');
  await settle(200);
  await page.locator('#powerKey').dblclick();
  await settle(500);
  await page.keyboard.up('ArrowDown');
  check(await view() === 'update_mode' && await has('update_qr'), 'Boot held + power twice enters update mode');
  await ai();
  check(await view() === 'update_mode', 'AI does nothing in update mode');
  await page.locator('#powerKey').click();
  await page.waitForTimeout(2000);
  check(await view() === 'home', 'one power press restarts into Vibe Mode');
  await reset();

  // 18. Agent install over USB.
  await panel('simDeploy', 400);
  check(await view() === 'progress' && !(await has('button_cancel')), 'USB deploy shows progress without Cancel');
  await page.waitForTimeout(6800);
  check(await view() === 'running' && await mdl(() => model.current) === '900001', 'deployed Idea runs');
  check(await mdl(() => !ideaById('900001')), 'an agent install is not in NAND yet');
  await blur();
  await page.keyboard.down('ArrowUp');
  await page.locator('#powerKey').dblclick();
  await page.waitForTimeout(1300);
  await page.keyboard.up('ArrowUp');
  await settle();
  await tap('pager_hit_1', 520);
  await tap('button_idea_100002', 300);
  check((await text('confirm_sub')).includes('Unsaved hello_world'), 'switching away warns that the unsaved build will be replaced');
  await tap('button_confirm_cancel', 300);
  await ai();
  await tap('button_develop');
  check((await text('develop_save_sub')).includes('hello_world · keep'), 'Develop offers Save to NAND flash');
  await tap('button_save_nand', 400);
  check(await view() === 'progress' && (await text('progress_title')) === 'Saving to NAND', 'saving shows the write progress');
  await page.waitForTimeout(2200);
  check(await view() === 'result' && await mdl(() => !!ideaById('900001')), 'saved: the Idea is now in NAND');
  await tap('button_result_left', 420);
  check((await text('develop_save_sub')) === 'hello_world is saved', 'Develop shows it is saved');
  await reset();


  // 19. Language: Settings → Language turns every page Chinese at once and survives a reload.
  // Idea names, SSIDs, URLs and shared data are content and stay as they are.
  const englishLeft = () => page.evaluate(() => {
    const keep = new Set(['Vibe', 'Mode', 'Mosaico', 'Ideas', 'Idea', 'AI', 'Agent', 'Wi-Fi', 'USB', 'NAND', 'IMU', 'Boot',
      'MB', 'KB', 'MAC', 'ID', 'IP', 'WPA', 'WPA2', 'API', 'English', 'Coding', 'ABC', 's']);
    const content = [...model.ideas.map((a) => a.name), ...Object.values(STORE).map((a) => a.name), ...NETS.map((n) => n.ssid),
      ...nvs.flatMap((e) => [e.key, e.value]), 'hello_world'].filter(Boolean).sort((a, b) => b.length - a.length);
    const shown = (el) => { for (let e = el; e && e !== screen; e = e.parentElement) {
      const cs = getComputedStyle(e); if (cs.display === 'none' || cs.visibility === 'hidden' || Number(cs.opacity) === 0) return false; }
      return true; };
    const out = [];
    for (const el of screen.querySelectorAll('span, .kb-key, .chip')) {
      if (el.children.length || !shown(el)) continue;
      const key = el.closest('.kb-key');
      if (key && !['kb: ', 'kb:go'].includes(key.dataset.key)) continue;
      let t = el.textContent.replace(/\/\n/g, '/').replace(/\b[a-z]–[a-z]\b/g, ' ');
      t = t.replace(/https?:\/\/\S+|[\w-]+(\.[\w-]+)+(\/\S*)?|shared\/\w+/g, ' ');
      for (const n of content) t = t.split(n).join(' ');
      t = t.replace(/v?\d[\w.:-]*/g, ' ');
      for (const w of t.match(/[A-Za-z][A-Za-z'’-]*/g) || []) if (!keep.has(w)) out.push(`${w} ← “${el.textContent.trim()}”`);
    }
    return [...new Set(out)];
  });
  const cut = () => page.evaluate(() => [...screen.querySelectorAll('span')].filter((s) => !s.children.length
    && /[\u3000-\u9fff]/.test(s.textContent) && (s.scrollWidth > s.clientWidth + 1 || s.scrollHeight > s.clientHeight + 2)
    && (getComputedStyle(s).textOverflow === 'ellipsis' || getComputedStyle(s).webkitLineClamp !== 'none')).map((s) => s.textContent));
  const zhIssues = [];
  const audit = async (where) => {
    for (const w of await englishLeft()) zhIssues.push(`${where}: English ${w}`);
    for (const c of await cut()) zhIssues.push(`${where}: cut off “${c}”`);
  };
  await tap('button_settings');
  check((await text('settings_language')) === 'English', 'Settings shows the current language');
  await tap('button_language');
  check(await view() === 'language', 'the Language page opens');
  await tap('button_lang_zh', 420);
  check(await mdl(() => LANG) === 'zh' && (await text('language_title')) === '语言', 'choosing 简体中文 switches right away');
  check((await text('toast_text')) === '已切换为简体中文', 'the confirmation is in Chinese');
  check(await page.locator('.thumb').count() === stateCount && (await page.locator('.thumb span').first().textContent()).length > 0,
    'the gallery shows the Chinese states');
  await shot('40-zh-language');
  await audit('language');
  await ai(420, 700);
  check((await page.locator('#screen [data-name="settings_title"]').first().textContent()) === '设置' && (await text('settings_language')) === '简体中文', 'Settings is Chinese and lists 简体中文');
  await audit('settings');
  await shot('41-zh-settings');
  for (const [btn, name] of [['button_wifi', 'wifi'], ['button_display', 'display'], ['button_shared', 'shared'], ['button_about', 'about']]) {
    await tap(btn, 420); await audit(name); await shot(`42-zh-${name}`); await ai();
  }
  await tap('button_wifi', 420);
  await tap('button_wifi_current', 420); await audit('wifi network');
  await ai();
  await rows('networks').first().click(); await settle(420); await audit('password');
  check((await page.locator('#screen .kb-key[data-key="kb: "]').last().textContent()) === '空格'
    && (await page.locator('#screen .kb-key[data-key="kb:go"]').last().textContent()) === '确定', 'keyboard space and GO keys are Chinese');
  await shot('43-zh-password');
  await ai(); await ai();
  await tap('button_shared', 420);
  await tap('button_shared_help', 420); await audit('shared help'); await ai();
  await rows('shared').first().click(); await settle(420); await audit('shared entry'); await shot('44-zh-shared-entry'); await ai();
  await tap('button_add_entry', 420); await audit('shared add'); await ai(); await ai();
  await tap('button_help', 420); await audit('help');
  for (const k of ['start', 'develop', 'ids', 'fix']) {
    await tap(`button_help_${k}`, 420); await audit(`help ${k}`); await shot(`45-zh-help-${k}`);
    if (k === 'start') { await tap('button_help_qr', 420); await audit('qr'); await shot('46-zh-qr'); await ai(); }
    await ai();
  }
  await ai(); await ai();
  check(await view() === 'home' && (await text('home_title_b')).includes('跑起来'), 'Home is Chinese');
  await audit('home'); await shot('47-zh-home');
  await tap('button_develop', 420); await audit('develop'); await shot('48-zh-develop'); await ai();
  await toManage(); await audit('manage'); await shot('49-zh-manage');
  await rows('manage').nth(1).click(); await settle(420); await audit('idea info (update)'); await shot('50-zh-info');
  {
    const c = await center('button_delete');
    await page.mouse.move(c.x, c.y); await page.mouse.down(); await page.waitForTimeout(1300);
    await audit('delete hold'); await shot('51-zh-deleting');
    await page.mouse.up(); await settle(420);
    check((await text('toast_text')) === '未删除', 'letting go early says 未删除');
  }
  await ai();
  await tap('button_add_download', 420); await audit('download');
  await typeKeys('404040'); await tap('key_go', 1800); await audit('download error'); await shot('52-zh-download-error');
  check(/[\u4e00-\u9fff]/.test(await text('id_status')) && (await text('id_status')) !== '输入 Mosaico Ideas 上的 6 位编号', 'lookup errors are Chinese');
  await ai(); await ai();
  await tap('pager_hit_1', 520); await audit('ideas page');
  check((await text('nav_badge')) === 'Idea 1/4', 'the page badge names the Ideas page');
  await tap('button_idea_100002', 300); await audit('confirm'); await shot('53-zh-confirm');
  await tap('button_confirm_open', 500); await audit('switching'); await shot('54-zh-switching');
  await page.waitForTimeout(4200); await audit(`after switch (${await view()})`);
  await reset();
  await blur(); await page.keyboard.down('ArrowDown'); await settle(800);
  await audit('boot tip'); await shot('55-zh-boot-tip');
  await page.keyboard.up('ArrowDown'); await tap('button_boot_tip_ok', 400);
  await ai(55, 700); await audit('sleep'); await shot('56-zh-sleep');
  check((await page.locator('#keyFb .chip').textContent()) === '息屏', 'the AI key chip is Chinese');
  await tap('button_wake', 500);
  check(zhIssues.length === 0, `every Chinese page is fully translated and nothing is cut off${zhIssues.length ? ':\n    ' + zhIssues.join('\n    ') : ''}`);
  await page.reload(); await page.waitForTimeout(500);
  check(await mdl(() => LANG) === 'zh' && (await text('home_title_b')).includes('跑起来'), 'the language survives a reload');
  await tap('button_settings'); await tap('button_language'); await tap('button_lang_en', 420);
  check(await mdl(() => LANG) === 'en' && (await text('toast_text')) === 'Language: English' && (await text('language_title')) === 'Language',
    'switching back to English works');
  await reset();

  check(errors.length === 0, `no script errors${errors.length ? ': ' + errors.join(' | ') : ''}`);
  console.log(`\n${pass} passed, ${fail} failed`);
  await browser.close();
  process.exit(fail ? 1 : 0);
})();
