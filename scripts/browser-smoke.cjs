'use strict';
const { chromium } = require('playwright');
const fs = require('node:fs/promises');
const path = require('node:path');
const { pathToFileURL } = require('node:url');

(async () => {
  const root = path.resolve(__dirname, '..');
  const course = JSON.parse(await fs.readFile(path.join(root, 'data/course.json'), 'utf8'));
  const exercises = JSON.parse(await fs.readFile(path.join(root, 'data/exercises.json'), 'utf8'));
  const exams = JSON.parse(await fs.readFile(path.join(root, 'data/exams.json'), 'utf8'));
  const rCheck = JSON.parse(await fs.readFile(path.join(root, 'data/r-verification.json'), 'utf8'));
  const homeHtml = await fs.readFile(path.join(root, 'index.html'), 'utf8');
  const version = homeHtml.match(/assets\/site\.js\?v=([a-f0-9]+)/)[1];
  const base = process.env.SITE_BASE_URL;
  const output = path.join(root, 'artifacts/browser', base ? 'live' : 'local');
  await fs.mkdir(output, { recursive: true });
  const url = file => {
    if (!base) return pathToFileURL(path.join(root, file)).href;
    const result = new URL(file, base);
    result.searchParams.set('verify', version);
    return result.href;
  };
  const browser = await chromium.launch({
    headless: true,
    ...(process.env.BROWSER_EXECUTABLE ? { executablePath: process.env.BROWSER_EXECUTABLE } : {}),
  });
  const errors = [];
  const report = [];
  let pagesChecked = 0;
  try {
    if (base) {
      // Pages builds independently of this check; wait for the current content.
      const probe = await browser.newContext();
      let published = false;
      for (let attempt = 0; attempt < 18; attempt++) {
        const response = await probe.request.get(url('index.html') + '&review=' + Date.now());
        const html = await response.text();
        if (response.ok() && html.includes('assets/site.js?v=' + version)) {
          published = true;
          break;
        }
        await new Promise(resolve => setTimeout(resolve, 10000));
      }
      await probe.close();
      if (!published) throw new Error('Pages has not served the current build version: ' + version);
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
        if (chapter.id === 11) {
          if (!(await page.locator('#r-execution').innerText()).includes('数值检查通过')) throw new Error('R execution provenance missing');
          for (const id of ids) {
            const result = page.locator('#' + id + ' details').filter({ has: page.locator('summary', { hasText: '查看实际 R 运行结果' }) });
            await result.locator('summary').click();
            if (!(await result.innerText()).includes('实际执行后提取')) throw new Error('R output missing: ' + id);
            if (rCheck.graphics?.[id]) {
              await result.locator('img').waitFor({ state: 'visible' });
              if (!(await result.locator('img').evaluate(img => img.complete && img.naturalWidth > 0 && img.alt.length > 10))) throw new Error('R plot did not load: ' + id);
            }
          }
        }
        if (width === 390) {
          const screenshots = {
            2: ['hypergeometric-binomial-limit','poisson-error-bound','mixed-transform'],
            5: ['bernoulli-khinchin','central-limit'],
            3: ['multivariate-basics','conditional-cdf-bayes','independent-blocks','joint-transform-cdf','jacobian-transform','gamma-additivity','normal-linear-combination','system-lifetimes','rayleigh-radius'],
            6: ['student-t-density','f-density-t-square'],
            7: ['normal-mle-proof','beta-prior-moments','normal-conjugate-update'],
            11: ['r-boxplot','r-anova','r-regression'],
            12: ['poisson-small-increments','poisson-arrival-times'],
            13: ['markov-return-criterion'],
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
        pagesChecked += 2;
      }
      await page.goto(url('sources.html') + '#audit-3.5', { waitUntil: 'load' });
      pagesChecked++;
      const sourceText = await page.locator('#coverage').innerText();
      if (!sourceText.includes('2026-10-17') || !sourceText.includes('70–110')) throw new Error('Source audit provenance missing');
      if (!(await page.locator('#audit-3\\.5').isVisible())) throw new Error('Audit section cannot be opened');
      if (width === 390) await page.screenshot({ path: path.join(output,'source-audit.png') });
      for (const exam of exams) {
        await page.goto(url('exam-' + exam.id + '.html'), { waitUntil: 'load' });
        pagesChecked++;
        const check = await page.evaluate(ids => ({
          missing: ids.filter(id => !document.getElementById(id)),
          overflow: document.documentElement.scrollWidth > innerWidth + 1,
        }), exam.questions.map(q => q.id));
        if (check.missing.length || check.overflow) throw new Error(JSON.stringify({ width, exam: exam.id, ...check }));
        if (width === 390 && exam.id === 3) {
          await page.addStyleTag({ content: '.topbar{position:static!important}.skip{display:none!important}' });
          await page.locator('#E3-1 details').evaluate(e => e.open = true);
          await page.locator('#E3-4 details').evaluate(e => e.open = true);
          for (const id of ['E3-1','E3-4']) await page.locator('#' + id).screenshot({ path:path.join(output,id+'.png') });
        }
      }
      if (width === 390) {
        // Seed an older valid record, then exercise the new >60-minute paper.
        // All data live in this disposable browser context, never a user's tab.
        await page.evaluate(() => localStorage.setItem('probability-study-v1', JSON.stringify({
          version:1,notes:{'P1-01':'旧草稿'},progress:{'P1-01':'mastered'},recall:{},
          scores:{'E1-1':6},timers:{'1':{remaining:3500000,end:null}},
        })));
        await page.goto(url('exam-3.html'), { waitUntil:'load' });
        pagesChecked++;
        await page.locator('[data-score="E3-1"]').fill('999');
        if (await page.locator('[data-score="E3-1"]').inputValue() !== '15') throw new Error('Exam score was not clamped');
        await page.locator('[data-score="E3-1"]').fill('7');
        await page.locator('[data-note="E3-1"]').fill('第三章测试草稿');
        await page.locator('[data-timer="toggle"]').click();
        const firstEnd = await page.evaluate(() => JSON.parse(localStorage.getItem('probability-study-v1')).timers['3'].end);
        await page.reload({ waitUntil:'load' });
        pagesChecked++;
        const resumed = await page.evaluate(() => JSON.parse(localStorage.getItem('probability-study-v1')));
        if (resumed.timers['3'].end !== firstEnd || resumed.notes['E3-1'] !== '第三章测试草稿' || resumed.scores['E3-1'] !== 7) throw new Error('New paper did not resume');
        await page.locator('[data-timer="toggle"]').click();
        const paused = await page.evaluate(() => JSON.parse(localStorage.getItem('probability-study-v1')));
        if (paused.timers['3'].end !== null || paused.timers['3'].remaining > 4500000 || paused.timers['3'].remaining < 4400000) throw new Error('New paper timer reset or failed to pause');
        if (paused.notes['P1-01'] !== '旧草稿' || paused.progress['P1-01'] !== 'mastered' || paused.scores['E1-1'] !== 6 || paused.timers['1'].remaining !== 3500000) throw new Error('Legacy study data changed');
        await page.goto(url('memory.html'), { waitUntil:'load' });
        pagesChecked++;
        await page.locator('#import-records').setInputFiles({name:'record.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify({version:1,timers:{'3':{remaining:4000000,end:null}},scores:{'E3-1':14}}))});
        await page.waitForFunction(() => document.querySelector('#toast').textContent.includes('已合并'));
        const imported = await page.evaluate(() => JSON.parse(localStorage.getItem('probability-study-v1')));
        if (imported.timers['3'].remaining !== 4000000 || imported.scores['E3-1'] !== 14 || imported.notes['P1-01'] !== '旧草稿') throw new Error('Long-paper record import failed');
      }
      await context.close();
    }
    if (errors.length) throw new Error('Browser JavaScript errors: ' + errors.join('; '));
    await fs.writeFile(path.join(output, 'report.json'), JSON.stringify({ pagesChecked, checks: report, exams:exams.length,studyRecordCompatibility:true }, null, 2));
    console.log(JSON.stringify({ target: base || 'local files', pagesChecked, errors: errors.length,studyRecordCompatibility:true }));
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
