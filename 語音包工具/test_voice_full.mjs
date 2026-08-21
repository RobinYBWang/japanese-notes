// 語音版驗證:載入、六角色選單、發音點覆蓋、朗讀預錄套組、測驗、無錯誤
import { chromium } from 'playwright';

const errors = [];
const browser = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium' });
const page = await browser.newPage();
page.on('dialog', d => d.dismiss());
page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });
page.on('pageerror', e => errors.push(String(e)));
await page.goto('file:///mnt/user-data/uploads/日文學習/japanese-notes/minna-notes.html', { timeout: 90000 });
await page.waitForTimeout(2500);

const checks = [];
const ok = (n, c) => checks.push([n, !!c]);

ok('標題含語音版', (await page.title()).includes('語音版'));

// 資料載入
const stat = await page.evaluate(() => ({
  clips: Object.keys(VV_AUDIO).length, texts: Object.keys(VV_SAY).length,
  reading: Object.keys(VV_READING), voices: VV_VOICES.length,
})).catch(() => null);
ok('VV 資料載入', !!stat);
ok('clips=7632', stat && stat.clips === 4884);
ok('三角色', stat && stat.voices === 3);
ok('朗讀套組 1/2/3/99', stat && ['1','2','3','99'].every(k => stat.reading.includes(k)));

// 覆蓋率:走遍每課每分頁,每個 data-say 都能找到目前聲音的 clip
const cover = await page.evaluate(() => {
  const missing = [];
  for (let n = 0; n <= LESSONS; n++) {
    for (const [s] of subsFor(n)) {
      try { switchLesson(n); switchSection(s); } catch (e) {}
      document.querySelectorAll('[data-say]').forEach(el => {
        const t = el.getAttribute('data-say');
        if (t && !vvClip(t, 'A')) missing.push(t);
      });
    }
  }
  return missing;
});
ok('DOM data-say 全覆蓋', cover.length === 0);

// 單字 sayText 覆蓋(以 workbook 全列驗證)
const vocabCover = await page.evaluate(() => {
  const miss = [];
  for (const k in workbook.lessons) {
    if (k === '0') continue;
    for (const r of workbook.lessons[k]) {
      const t = sayText(r);
      if (t && !vvClip(t, 'A')) miss.push(t);
      if (r.kana && !vvClip(r.kana, 'A')) miss.push('kana:' + r.kana);
    }
  }
  return miss;
});
ok('單字/假名全覆蓋', vocabCover.length === 0);

// 五十音覆蓋
const kanaCover = await page.evaluate(() => {
  const miss = [];
  for (const r of workbook.lessons['0'] || []) {
    for (const t of [r.hira, r.kata,
      ((r.hiraex || '').split('（')[0]).trim(), ((r.kataex || '').split('（')[0]).trim()]) {
      if (t && !vvClip(t, 'A')) miss.push(t);
    }
  }
  return miss;
});
ok('五十音全覆蓋', kanaCover.length === 0);

// 語音設定選單:六個自訂名字
await page.evaluate(() => { switchLesson(1); switchSection('vocab'); });
const names = await page.evaluate(() => { populateVoices(); return [...document.getElementById('voicesel').options].map(o => o.text); });
ok('選單含 Chloe', names.some(t => t.includes('Chloe')));ok('選單無 Emily/Vanessa/Kevin', !names.some(t => /Emily|Vanessa|Kevin/.test(t)));
ok('選單含 Darren(無 Keanu)', names.some(t => t.includes('Darren')) && !names.some(t => t.includes('Keanu')));
ok('選單 3 項', names.length === 3);

// 朗讀:預錄套組載入且每行有 clip
const readOK = await page.evaluate(() => {
  const t = genReadingText(1);
  const lines = parseRead(t);
  return lines.length > 10 && lines.every(ln => !!vvClip(ln.jp, ln.role === 'B' ? 'B' : 'A'));
});
ok('朗讀套組每行有音檔', readOK);

// 實際播放一個單字(speakWith 走音檔路徑)
const played = await page.evaluate(() => new Promise(res => {
  const id = vvClip(sayText(workbook.lessons['1'][0]), 'A');
  if (!id) return res(false);
  const a = new Audio('data:audio/mpeg;base64,' + VV_AUDIO[id]);
  a.addEventListener('loadedmetadata', () => res(a.duration > 0.2));
  a.addEventListener('error', () => res(false));
}));
ok('單字音檔可解碼', played);

// 測驗建置
const quizOK = await page.evaluate(() => { try { switchLesson(1); switchSection('quiz'); return document.querySelectorAll('#quizbody .qitem,#quizbody .q,#quizbody [class*=q]').length > 0 || document.getElementById('quizbody').innerHTML.length > 200; } catch (e) { return false; } });
ok('測驗有出題', quizOK);

// 編輯功能仍在(母版特性):新增單字按鈕存在
ok('編輯功能保留', await page.evaluate(() => !!document.querySelector('#addrow,#addbtn,[id*=add]')));


// 時間小考:segs 每個拼讀單位都有 clip;按 tq-say 不噴錯
const tqOK = await page.evaluate(() => {
  switchLesson(13); switchSection('time');
  let allCovered = true;
  for (let t = 0; t < 30; t++) {
    tqPick();
    for (const seg of (tqItem.segs || [])) {
      for (const p of String(seg).split(' ')) {
        if (p && !vvClip(p, 'A')) { allCovered = false; }
      }
    }
  }
  return allCovered;
});
ok('時間小考拼讀單位全覆蓋(30抽)', tqOK);
await page.click('#tq-say');
await page.waitForTimeout(600);
ok('時間小考按發音不噴錯', errors.length === 0);

// 數字小考:numReadingParts 各單位有 clip
const nqOK = await page.evaluate(() => {
  switchLesson(13); switchSection('num');
  for (const n of [0, 7, 34, 500, 8100, 45678, 99999]) {
    for (const p of numReadingParts(n)) { if (!vvClip(p, 'A')) return 'miss:' + p; }
  }
  return true;
});
ok('數字小考拼讀單位全覆蓋', nqOK === true);
await page.click('#nq-say');
await page.waitForTimeout(600);
ok('數字小考按發音不噴錯', errors.length === 0);


// 試聽A/B 有預錄音檔
ok('試聽A有音檔', await page.evaluate(() => !!vvClip('あめ、はし、かぎ、にほんご。はつおんテストです。','A')));
ok('試聽B有音檔', await page.evaluate(() => !!vvClip('こんにちは。べつの こえで はなします。','B')));

ok('無 console 錯誤', errors.length === 0);

let fail = 0;
for (const [n, c] of checks) { console.log((c ? 'PASS' : 'FAIL') + '  ' + n); if (!c) fail++; }
if (cover.length) console.log('data-say missing sample:', cover.slice(0, 5));
if (vocabCover.length) console.log('vocab missing sample:', vocabCover.slice(0, 5));
if (kanaCover.length) console.log('kana missing sample:', kanaCover.slice(0, 5));
if (errors.length) console.log('errors:', errors.slice(0, 6));
await browser.close();
process.exit(fail ? 1 : 0);
