// Playwright smoke test for prototype/index.html (design tooling only).
// Usage: node tools/prototype_smoke.js [screenshot-dir]
// Set PLAYWRIGHT_MODULE when the playwright package is not resolvable from here.
const path = require('path');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const page_file = path.resolve(__dirname, '..', 'prototype', 'index.html');
const out = process.argv[2] || null;
let pass = 0, fail = 0;
const check = (cond, msg) => { if (cond) pass++; else fail++; console.log((cond ? 'PASS ' : 'FAIL ') + msg); };
(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1280, height: 1000 } });
  const errors = [];
  page.on('pageerror', e => errors.push('pageerror: ' + e.message));
  page.on('console', m => { if (m.type() === 'error') errors.push('console: ' + m.text()); });
  await page.goto('file://' + page_file);
  await page.waitForTimeout(600);
  const loc = (name) => page.locator(`#screen [data-name="${name}"]`).first();
  const text = async (name) => (await loc(name).textContent().catch(() => null));
  const has = async (name) => (await page.locator(`#screen [data-name="${name}"]`).count()) > 0;
  const tap = async (name, wait = 260) => { await loc(name).click(); await page.waitForTimeout(wait); };
  // Click the centre of a non-button object: the tap must reach the button underneath.
  const tapThrough = async (name, wait = 260) => { const b = await loc(name).boundingBox(); await page.mouse.click(b.x + b.width / 2, b.y + b.height / 2); await page.waitForTimeout(wait); };
  const blur = () => page.evaluate(() => document.activeElement && document.activeElement.blur());
  const ai = async (ms = 60) => { await blur(); await page.keyboard.down('ArrowUp'); await page.waitForTimeout(ms); await page.keyboard.up('ArrowUp'); };
  const aiDouble = async () => { await ai(); await page.waitForTimeout(80); await ai(); await page.waitForTimeout(450); };
  const reset = async () => { await page.click('#simReset'); await page.waitForTimeout(350); };
  const row = async (i) => { await page.locator('#screen .row-hit').nth(i).click(); await page.waitForTimeout(300); };

  const rows = async () => page.locator('#screen .row-hit').count();
  const pick = async (key) => { await tap('button_filter'); await tap(`category_${key}`, 400); };

  // A. Download by ID -> download & run -> installed -> running; library grows.
  check(await rows() === 20, 'home lists 20 preset apps');
  check(await text('home_title') === 'All apps', 'list picker shows All apps');
  if (out) await page.screenshot({ path: path.join(out, 'v3-desktop.png') });
  await tap('button_download');
  check(await text('id_status') === 'Type the app ID', 'download page opened');
  await blur();
  for (const k of '238114') await page.keyboard.press(k);
  check(await text('id_digits') === '238114', 'typed digits shown');
  await page.keyboard.press('Enter');
  await page.waitForTimeout(1200);
  check(await text('detail_name') === 'Retro Snake', 'remote detail shows Retro Snake');
  check(await text('detail_status') === 'Not on this device', 'status: not on this device');
  await tap('button_about');
  check((await text('about_summary')).startsWith('The classic snake game'), 'About shows the store summary');
  await tap('button_back_about');
  await tap('button_primary');
  check(await text('progress_caption') === 'FROM MOSAICO IDEAS', 'download caption FROM MOSAICO IDEAS');
  await page.waitForTimeout(4600);
  check(await text('progress_title') === 'Switching apps', 'install after download');
  await page.waitForTimeout(3900);
  check(await text('result_title') === 'App installed', 'result installed');
  await page.waitForTimeout(3000);
  check(await text('running_title') === 'Retro Snake', 'app running');
  await tap('button_return', 1200);
  check(await rows() === 21, 'library now has 21 apps');

  // B. Offline lookup resumes after Wi-Fi connects; unknown IDs show a banner.
  await reset();
  await tap('button_download'); await blur();
  for (const k of '404040') await page.keyboard.press(k);
  await page.keyboard.press('Enter'); await page.waitForTimeout(1100);
  check(await text('ai_toast_text') === 'No app with this ID', 'unknown ID shows a banner');
  await reset(); await page.click('#simWifi');
  await blur(); await tap('button_download'); await blur();
  for (const k of '100006') await page.keyboard.press(k);
  await page.keyboard.press('Enter'); await page.waitForTimeout(300);
  check(await has('wifi_scan_accent'), 'offline lookup opens Wi-Fi with a continue hint');
  await row(0);
  check(await has('password_display'), 'password page');
  await blur(); await page.keyboard.type('short'); await page.keyboard.press('Enter');
  check(await text('password_note') === 'Use at least 8 characters', 'short password rejected');
  await page.keyboard.type('er1234'); await page.keyboard.press('Enter');
  await page.waitForTimeout(2600);
  check(await text('detail_status_accent') === 'Update v1.0.0 → v1.1.0', 'lookup resumed: update available');

  // C. Quick switch with the AI key.
  await reset();
  await aiDouble();
  check(await has('switch_name'), 'quick switch open: ' + await text('switch_name'));
  check(await text('switch_filter') === 'ALL APPS', 'quick switch shows the list name');
  await aiDouble();
  await ai(1150); await page.waitForTimeout(400);
  check(await text('progress_title') === 'Switching apps' || await has('launch_title'), 'hold opens the selected app');

  // D. Favorites and categories through the list picker.
  await reset();
  await pick('favorites');
  check(await text('home_title') === 'Favorites' && await rows() === 3, 'favorites: 3 apps');
  await row(0);
  check(await text('detail_name') === 'Pixel Pet' && await has('button_favorite_on'), 'favorite app shows filled star');
  await tap('button_favorite_on');
  check(await text('ai_toast_text') === 'Removed from Favorites', 'unfavorite banner');
  check(await has('button_favorite_off'), 'star now outlined');
  await ai(); await page.waitForTimeout(500);
  check(await rows() === 2, 'AI back: favorites now 2');
  await tap('button_filter');
  check(await text('categories_title') === 'SHOW', 'list picker page');
  check(await text('category_favorites_count') === '02', 'counts follow favorites');
  await tap('category_audio', 400);
  check(await text('home_title') === 'Audio' && await rows() === 3, 'audio: 3 apps');
  await aiDouble();
  check(await text('switch_filter') === 'AUDIO', 'quick switch follows the list');
  await ai(); await page.waitForTimeout(450);
  await pick('all');
  check(await rows() === 20, 'back to all apps');

  // E. Delete with confirmation.
  await reset();
  await row(1);
  check(await text('detail_name') === 'Lo-fi Clock', 'local detail opened');
  await ai(); await page.waitForTimeout(500);
  check(await has('button_filter'), 'AI single press went home');
  await row(1);
  await tap('button_tertiary');
  check(await has('button_delete_confirm'), 'delete asks for confirmation');
  await tap('button_delete_confirm');
  check(await rows() === 19, 'deleted, 19 left');
  check(await text('ai_toast_text') === 'Deleted: Lo-fi Clock', 'delete banner');

  // F. Develop page and QR enlarge.
  await reset();
  await tap('button_develop');
  check(await text('develop_status_on') === '● USB connected · AI agent ready', 'develop shows USB and agent ready');
  await page.click('#simUsb'); await page.waitForTimeout(200);
  check(await text('develop_status_off') === '● Plug in a USB data cable', 'status follows the cable');
  await tap('button_step_1');
  check(await text('qr_full_title') === 'Vibe-coding guide', 'guide QR enlarges');
  if (out) await page.screenshot({ path: path.join(out, 'v3-qr.png') });
  await tap('button_qr_close');
  check(await has('develop_title'), 'tap closes the enlarged QR');

  // G. Per-app QR on the About page.
  await reset();
  await row(0);
  await tap('button_about');
  await tap('button_qr_app');
  check(await text('qr_full_title') === 'Pixel Pet on Mosaico Ideas', 'app QR enlarges with the app name');
  check(await text('qr_full_url') === 'mosaico-ideas.espressif.com/app/100001', 'app QR URL');

  // H. Shared settings: computer first, keyboard as a fallback.
  await reset();
  await tap('button_device');
  check(await text('device_city') === 'Shanghai', 'device shows the shared city');
  await tapThrough('device_city');
  check(await text('city_title') === 'CITY', 'tap on the row text opens the city page');
  await tap('button_type_city');
  await blur();
  for (let i = 0; i < 8; i++) await page.keyboard.press('Backspace');
  await page.keyboard.press('Enter');
  check(await text('city_input_note') === 'Type a city name first', 'empty city rejected');
  await page.keyboard.type('Shenzhen'); await page.keyboard.press('Enter'); await page.waitForTimeout(300);
  check(await text('ai_toast_text') === 'City saved' && await text('city_value') === 'Shenzhen', 'city saved');
  await tap('button_back_city');
  await tap('button_device_token');
  check((await text('token_value')).endsWith('4c8e'), 'token page shows the token tail');
  await tap('button_type_token');
  check((await text('token_input_display')).startsWith('•'), 'token masked');
  await tap('button_toggle_token_input');
  check(!(await text('token_input_display')).startsWith('•'), 'token revealed');
  await tap('button_back_token_input');
  await tap('button_clear_token');
  check(await text('token_value') === 'Not set', 'token cleared');
  await tap('button_back_token');
  await tap('button_device_info');
  await tap('button_wifi_link');
  check(await text('wifilink_endpoint') === '192.168.1.20:7777', 'Wi-Fi link page');

  // I. First-boot guide.
  await page.click('#simGuide'); await page.waitForTimeout(1300);
  check(await text('guide_step') === '01/04', 'guide starts');
  if (out) await page.screenshot({ path: path.join(out, 'v3-guide1.png') });
  for (let i = 0; i < 3; i++) await tap('button_guide_next');
  check(await text('guide_step') === '04/04', 'guide page 4');
  await tap('button_guide_next');
  check(await has('button_filter'), 'guide done returns home');

  // J. Agent deploy.
  await page.click('#simDeploy'); await page.waitForTimeout(400);
  check(await text('progress_caption') === 'FROM YOUR AI AGENT · USB', 'agent progress shown');

  // K. Gallery static preview.
  const n = await page.locator('.thumb').count();
  check(n === 41, 'gallery lists 41 states');
  await page.locator('.thumb').nth(16).click(); await page.waitForTimeout(300);
  check(await page.locator('#staticBar.show').count() === 1, 'static preview opens');
  if (out) await page.screenshot({ path: path.join(out, 'v3-static.png') });
  await page.click('#staticExit');

  const phone = await browser.newPage({ viewport: { width: 390, height: 844 } });
  await phone.goto('file://' + page_file); await phone.waitForTimeout(500);
  check(!(await phone.evaluate(() => document.documentElement.scrollWidth > window.innerWidth)), 'no horizontal overflow at phone width');
  if (out) await phone.screenshot({ path: path.join(out, 'v3-phone.png') });
  check(errors.length === 0, 'no console errors ' + (errors.length ? JSON.stringify(errors) : ''));
  console.log(`${pass} passed, ${fail} failed`);
  await browser.close();
  process.exitCode = fail ? 1 : 0;
})();
