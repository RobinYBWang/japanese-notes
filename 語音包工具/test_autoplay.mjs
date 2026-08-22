// 回歸測試：小抽考的自動發音只能由使用者動作觸發（2026-08-22 修好的 bug，別再退化）
// 驗證：切課／切分頁不得自動發音；按下一題／重考／切模式才發音
import { chromium } from 'playwright';
import { pathToFileURL } from 'node:url';
const b = await chromium.launch();
const p = await b.newPage({ viewport: { width: 1280, height: 900 } });
const errs = [];
p.on('dialog', d => d.dismiss());
p.on('pageerror', e => errs.push(String(e)));
await p.goto(pathToFileURL('C:/Users/User/Documents/Claude/Projects/日文學習/japanese-notes/minna-notes.html').href, { timeout: 90000 });
await p.waitForTimeout(1800);
await p.evaluate(() => {
  window.__plays = 0;
  const orig = window.speak;
  window.speak = function (t, btn) { window.__plays++; return orig(t, btn); };
  window.__reset = () => { window.__plays = 0; };
});
const plays = () => p.evaluate(() => { const n = window.__plays; window.__plays = 0; return n; });

const out = [];
// 單字小抽考：切到「只聽發音」
await p.evaluate(() => { switchLesson(1); switchSection('vocab'); });
await p.waitForTimeout(400); await plays();
await p.click('#voc-quiz .aq-mode[data-mode="listen"]'); await p.waitForTimeout(400);
out.push(['切到只聽發音（使用者動作）應該發音', await plays()]);
await p.evaluate(() => switchLesson(2)); await p.waitForTimeout(600);
out.push(['切課（listen 模式）不該發音', await plays()]);
await p.evaluate(() => switchLesson(3)); await p.waitForTimeout(600);
out.push(['再切一課不該發音', await plays()]);
await p.click('#vq-next'); await p.waitForTimeout(400);
out.push(['按下一題應該發音', await plays()]);
await p.click('#vq-restart'); await p.waitForTimeout(400);
out.push(['按重考應該發音', await plays()]);

// 聽寫打字模式
await p.click('#voc-quiz .aq-mode[data-mode="type"]'); await p.waitForTimeout(400);
out.push(['切到聽寫打字應該發音', await plays()]);
await p.evaluate(() => switchLesson(4)); await p.waitForTimeout(600);
out.push(['切課（type 模式）不該發音', await plays()]);
await p.evaluate(() => { switchSection('quiz'); }); await p.waitForTimeout(500);
await p.evaluate(() => { switchSection('vocab'); }); await p.waitForTimeout(500);
out.push(['切分頁來回不該發音', await plays()]);
// 動詞總表
await p.evaluate(() => { switchLesson(14); switchSection('allverb'); }); await p.waitForTimeout(600);
out.push(['進動詞總表不該發音', await plays()]);
await p.click('#allverb-quiz .aq-mode[data-mode="listen"]'); await p.waitForTimeout(400);
out.push(['動詞總表切只聽發音應該發音', await plays()]);
await p.evaluate(() => { switchLesson(4); switchSection('verb'); }); await p.waitForTimeout(600);
out.push(['從動詞總表切回各課不該發音', await plays()]);
// 「再聽一次」仍要能用
await p.click('#allverb-quiz .aq-mode[data-mode="listen"]').catch(() => { });
await p.evaluate(() => { switchLesson(14); switchSection('allverb'); }); await p.waitForTimeout(500); await plays();
const hasPlay = await p.$('#av-q .aq-play');
if (hasPlay) { await hasPlay.click(); await p.waitForTimeout(400); }
out.push(['按「🔊 再聽一次」仍會發音', await plays()]);

for (const [n, v] of out) console.log((n.includes('不該') ? (v === 0 ? 'PASS' : 'FAIL') : (v > 0 ? 'PASS' : 'FAIL')) + '  ' + n + '（發音 ' + v + ' 次）');
console.log('errors:', errs.length, errs.slice(0, 2));
await b.close();
