// 開啟母版,走遍所有課/分頁,收集 DOM 上所有 data-say 文本
import { chromium } from 'playwright';
import fs from 'fs';

const browser = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium' });
const page = await browser.newPage();
page.on('dialog', d => d.dismiss());
await page.goto('file:///mnt/user-data/uploads/日文學習/japanese-notes/minna-notes.html');
await page.waitForTimeout(800);

const texts = new Set();
const collect = async () => {
  for (const t of await page.evaluate(() =>
    [...document.querySelectorAll('[data-say]')].map(e => e.getAttribute('data-say')).filter(Boolean)))
    texts.add(t);
};

// 每一課 × 每個子分頁
const lessons = await page.evaluate(() => typeof LESSONS !== 'undefined' ? LESSONS : 14);
for (let n = 0; n <= lessons; n++) {
  const subs = await page.evaluate((n) => (typeof subsFor === 'function' ? subsFor(n) : []).map(s => s[0]), n);
  for (const s of subs) {
    try {
      await page.evaluate(([n, s]) => { switchLesson(n); switchSection(s); }, [n, s]);
    } catch (e) {
      try { await page.evaluate(([n, s]) => { switchLesson(n); applySection(s); }, [n, s]); } catch (e2) {}
    }
    await page.waitForTimeout(120);
    await collect();
  }
}
await collect();
fs.writeFileSync('/home/claude/full/dom_says.json', JSON.stringify([...texts], null, 0));
console.log('data-say texts:', texts.size);
await browser.close();
