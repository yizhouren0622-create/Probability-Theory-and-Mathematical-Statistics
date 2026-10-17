'use strict';
const { chromium } = require('playwright');
const fs = require('node:fs/promises');
const path = require('node:path');
const { pathToFileURL } = require('node:url');

(async () => {
  const root = path.resolve(__dirname, '..');
  const course = JSON.parse(await fs.readFile(path.join(root, 'data/course.json'), 'utf8'));
  const exercises = JSON.parse(await fs.readFile(path.join(root, 'data/exercises.json'), 'utf8'));
  const base = process.env.SITE_BASE_URL;
  const output = path.join(root, 'artifacts/browser', base ? 'live' : 'local');
  await fs.mkdir(output, { recursive: true });
  const url = file => base ? new URL(file, base).href : pathToFileURL(path.join(root, file)).href;
  const browser = await chromium.launch({
    headless: true,
    ...(process.env.BROWSER_EXECUTABLE ? { executablePath: process.env.BROWSER_EXECUTABLE } : {}),
  });
  const errors = [];
  const report = [];
  try {
    if (base) {
      // Pages builds independently of this check; wait for the current content.
      const probe = await browser.newContext();
      let published = false;
      for (let attempt = 0; attempt < 18; attempt++) {
        const response = await probe.request.get(url('chapter-6.html') + '?review=' + Date.now());
        const html = await response.text();
        if (response.ok() && course[5].sections.flatMap(s => s.concepts).every(c => html.includes('id="' + c.id + '"'))) {
          published = true;
          break;
        }
        await new Promise(resolve => setTimeout(resolve, 10000));
      }
      await probe.close();
      if (!published) throw new Error('Pages has not served the current chapter 6 content');
    }
    for (const width of [1280, 390]) {
      const context = await browser.newContext({ viewport: { width, height: 900 } });
      const page = await context.newPage();
      page.on('pageerror', error => errors.push(error.message));
      for (const chapter of course) {
        await page.goto(url('chapter-' + chapter.id + '.html'), { waitUntil: 'load' });
        const ids = chapter.sections.flatMap(s => s.concepts.map(c => c.id));
        const before = await page.evaluate(ids => ({
          missing: ids.filter(id => !document.getElementById(id)?.querySelector('math')),
          overflow: document.documentElement.scrollWidth > innerWidth + 1,
        }), ids);
        if (before.missing.length || before.overflow) throw new Error(JSON.stringify({ width, chapter: chapter.id, ...before }));
        await page.locator('[data-proofs="open"]').click();
        const closed = await page.evaluate(() => [...document.querySelectorAll('.concept > details:first-of-type')].filter(d => !d.open).length);
        if (closed) throw new Error('Proof controls failed for chapter ' + chapter.id);
        const corrected = {
          10: ['bootstrap-ci-inversion', '这不要求整个重抽样分布都对称'],
          14: ['mean-ergodicity', '不能只凭本节的均方误差趋零结论推出'],
        }[chapter.id];
        if (corrected && !(await page.locator('#' + corrected[0]).innerText()).includes(corrected[1])) throw new Error('Mathematical wording correction missing');
        if (width === 390) {
          const screenshots = {
            6: ['sample-order-statistics', 'chi-square-density'],
            10: ['bootstrap-ci-inversion'],
            14: ['mean-ergodicity'],
          }[chapter.id] || [];
          await page.addStyleTag({ content: '.topbar{position:static!important}.skip{display:none!important}' });
          for (const id of screenshots) await page.locator('#' + id).screenshot({ path: path.join(output, id + '.png') });
        }
        await page.goto(url('practice-' + chapter.id + '.html'), { waitUntil: 'load' });
        const expected = exercises.filter(e => e.chapter === chapter.id).map(e => e.id);
        const missing = await page.evaluate(ids => ids.filter(id => !document.getElementById(id)), expected);
        if (missing.length) throw new Error('Missing exercises: ' + missing.join(','));
        report.push({ width, chapter: chapter.id, concepts: ids.length, exercises: expected.length });
      }
      await context.close();
    }
    if (errors.length) throw new Error('Browser JavaScript errors: ' + errors.join('; '));
    await fs.writeFile(path.join(output, 'report.json'), JSON.stringify({ pagesChecked: report.length * 2, checks: report }, null, 2));
    console.log(JSON.stringify({ target: base || 'local files', pagesChecked: report.length * 2, errors: errors.length }));
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
