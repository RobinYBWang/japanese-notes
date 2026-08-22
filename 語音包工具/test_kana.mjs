// kana.html 回歸測試：表格、音檔覆蓋、四種題型、範圍勾選、計分、版面
// 用法：node test_kana.mjs [要驗的 html，預設 ..\kana.html]
import { chromium } from 'playwright';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const HTML = path.resolve(process.argv[2] || path.join(HERE, '..', 'kana.html'));
const errors = [];
const browser = await chromium.launch();
const page = await browser.newPage();
page.on('dialog', d => d.dismiss());
page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });
page.on('pageerror', e => errors.push(String(e)));
console.log('驗證：' + HTML);
await page.goto(pathToFileURL(HTML).href, { timeout: 90000 });
await page.waitForTimeout(1500);

const checks = [];
const ok = (n, c) => checks.push([n, !!c]);

ok('標題', (await page.title()).includes('五十音'));

const stat = await page.evaluate(() => ({
  rows: KANA.length, clips: Object.keys(VV_AUDIO).length, texts: Object.keys(VV_SAY).length,
  voices: VV_VOICES.length,
  grp: KANA.reduce((a, r) => (a[r.grp || '清音'] = (a[r.grp || '清音'] || 0) + 1, a), {}),
})).catch(() => null);
ok('資料載入', !!stat);
ok('104 個假名', stat && stat.rows === 104);
ok('四組齊全（清音46/濁音20/半濁音5/拗音33）', stat &&
  stat.grp['清音'] === 46 && stat.grp['濁音'] === 20 && stat.grp['半濁音'] === 5 && stat.grp['拗音'] === 33);
ok('三個聲音', stat && stat.voices === 3);

// 表格：104 列 + 4 個分組標題列
const trs = await page.evaluate(() => ({
  data: document.querySelectorAll('#gj-tbody tr[data-i]').length,
  sec: document.querySelectorAll('#gj-tbody tr.gj-sec').length,
}));
ok('表格 104 列', trs.data === 104);
ok('4 個分組標題', trs.sec === 4);

// 音檔覆蓋：每個假名與例詞，三個聲音都要有 clip
const cover = await page.evaluate(() => {
  const miss = [];
  for (const r of KANA) {
    const ts = [r.hira, r.kata,
      ((r.hiraex || '').split('（')[0]).trim(), ((r.kataex || '').split('（')[0]).trim()];
    for (const t of ts) {
      if (!t) continue;
      for (const v of ['A', 'B']) if (!vvClip(t, v)) miss.push(v + ':' + t);
      const d = VV_SAY[vvNorm(t)] || {};
      if (!d['13']) miss.push('13:' + t);
    }
  }
  return miss;
});
ok('假名/例詞三聲音全覆蓋', cover.length === 0);

// 四種題型都出得來
const tags = await page.evaluate(() => {
  loadKanaScope();
  kanaScope.grp = { 清音: true, 濁音: true, 半濁音: true, 拗音: true };
  kanaScope.script = 'both';
  const pool = kanaPool(), s = {};
  for (let i = 0; i < 300; i++) { const q = makeKanaQ(pool[i % pool.length], pool); s[q.tag] = (s[q.tag] || 0) + 1; }
  return s;
});
ok('四種題型齊全（讀音/聽力/平↔片/打字）',
  ['讀音', '聽力', '平↔片', '打字'].every(k => tags[k] > 0));

// 選項不重複、答案在選項裡
const sane = await page.evaluate(() => {
  const pool = kanaPool(); const bad = [];
  for (let i = 0; i < 300; i++) {
    const q = makeKanaQ(pool[i % pool.length], pool);
    if (q.input) { if (!q.answer) bad.push('無答案:' + q.prompt); continue; }
    if (new Set(q.opts).size !== q.opts.length) bad.push('選項重複:' + q.opts.join('/'));
    if (q.ans < 0) bad.push('答案不在選項:' + q.prompt);
  }
  return bad;
});
ok('選項不重複且答案存在', sane.length === 0);

// 範圍勾選有效：只勾拗音 → 33 個
const scoped = await page.evaluate(() => {
  kanaScope.grp = { 清音: false, 濁音: false, 半濁音: false, 拗音: true };
  const n = kanaPool().length;
  kanaScope.grp = { 清音: true, 濁音: false, 半濁音: false, 拗音: false };
  const m = kanaPool().length;
  kanaScope.grp = { 清音: true, 濁音: true, 半濁音: true, 拗音: true };
  return [n, m];
});
ok('範圍勾選有效（拗音33／清音46）', scoped[0] === 33 && scoped[1] === 46);

// 出題 + 交卷計分
await page.click('#tabs .tab[data-sec="quiz"]');
await page.waitForTimeout(400);
ok('出了 10 題', (await page.locator('.qcard').count()) === 10);
ok('範圍列有出現', (await page.locator('.ksbar').count()) === 1);
await page.evaluate(() => {
  document.querySelectorAll('.qcard').forEach(c => {
    const r = c.querySelector('input[type=radio]'); if (r) r.checked = true;
    const i = c.querySelector('.qinput'); if (i) i.value = 'zzz';
  });
});
await page.click('#submitquiz');
await page.waitForTimeout(300);
const score = await page.textContent('#qscore');
ok('交卷有分數', /得分：\d+ \/ 10/.test(score || ''));
ok('每題都有回饋', (await page.locator('.qfb.good, .qfb.bad').count()) === 10);

// 音檔真的能解碼
const played = await page.evaluate(() => new Promise(res => {
  const id = vvClip(KANA[0].hira, 'A');
  if (!id) return res(false);
  const a = new Audio('data:audio/ogg;base64,' + VV_AUDIO[id]);
  a.addEventListener('loadedmetadata', () => res(a.duration > 0.1));
  a.addEventListener('error', () => res(false));
}));
ok('音檔可解碼', played);

// 點表格格子不噴錯
await page.click('#tabs .tab[data-sec="gojuon"]');
await page.waitForTimeout(300);
await page.click('#gj-tbody tr[data-i="0"] td[data-f="hira"]');
await page.waitForTimeout(500);
ok('點格子發音不噴錯', errors.length === 0);

// 版面：各寬度不得橫向溢出
const widths = [320, 390, 768, 1280];
const over = [];
for (const w of widths) {
  await page.setViewportSize({ width: w, height: 800 });
  await page.waitForTimeout(250);
  const o = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  if (o > 2) over.push(w + 'px 溢出 ' + o);
}
ok('320/390/768/1280 無橫向溢出', over.length === 0);

ok('無 console 錯誤', errors.length === 0);

let fail = 0;
for (const [n, c] of checks) { console.log((c ? 'PASS' : 'FAIL') + '  ' + n); if (!c) fail++; }
if (cover.length) console.log('缺音檔樣本:', cover.slice(0, 6));
if (sane.length) console.log('壞題樣本:', sane.slice(0, 4));
if (over.length) console.log('溢出:', over);
if (errors.length) console.log('errors:', errors.slice(0, 6));
console.log('clips ' + (stat && stat.clips) + ' / texts ' + (stat && stat.texts));
await browser.close();
process.exit(fail ? 1 : 0);
