'use strict';
(() => {
  const $ = (s, root = document) => root.querySelector(s);
  const $$ = (s, root = document) => [...root.querySelectorAll(s)];
  $$('[data-proofs]').forEach(button => button.addEventListener('click', () => {
    $$('.concept > details:first-of-type').forEach(detail => { detail.open = button.dataset.proofs === 'open'; });
  }));
  const KEY = 'probability-study-v1';
  const reading = $('.reading');
  if (reading) $('#main').prepend(reading);
  const index = window.STUDY_INDEX || [];
  const byId = new Map(index.map(x => [x.id, x]));
  const blank = () => ({version: 1, notes: {}, progress: {}, recall: {}, scores: {}, timers: {}});
  let state = blank(), storageOK = true, toastTimeout;
  function toast(message) {
    const target = $('#toast'); target.textContent = message; target.classList.add('visible');
    clearTimeout(toastTimeout); toastTimeout = setTimeout(() => target.classList.remove('visible'), 3600);
  }
  const object = x => x && typeof x === 'object' && !Array.isArray(x);
  function validate(raw) {
    if (!object(raw) || raw.version !== 1) throw new Error('不支持的记录版本');
    const result = blank();
    for (const key of ['notes', 'progress', 'recall', 'scores', 'timers']) {
      if (raw[key] !== undefined && !object(raw[key])) throw new Error('记录格式不正确');
    }
    for (const [id, value] of Object.entries(raw.notes || {})) {
      if (!byId.has(id)) continue;
      if (typeof value !== 'string' || value.length > 100000) throw new Error('草稿格式不正确');
      result.notes[id] = value;
    }
    for (const [id, value] of Object.entries(raw.progress || {})) {
      if (!byId.has(id) || byId.get(id).kind !== '原创练习') continue;
      if (!['review', 'mastered'].includes(value)) throw new Error('掌握状态不正确');
      result.progress[id] = value;
    }
    for (const [id, value] of Object.entries(raw.recall || {})) {
      if (!byId.has(id) || byId.get(id).kind !== '知识卡') continue;
      if (!object(value) || !Number.isFinite(value.due) || value.due < 0 || !Number.isFinite(value.interval) || value.interval < 0 || value.interval > 365) throw new Error('复习安排不正确');
      result.recall[id] = {due: value.due, interval: value.interval};
    }
    for (const [id, value] of Object.entries(raw.scores || {})) {
      if (!byId.has(id) || byId.get(id).kind !== '模拟卷') continue;
      if (!Number.isInteger(value) || value < 0 || value > byId.get(id).points) throw new Error('评分不正确');
      result.scores[id] = value;
    }
    for (const [id, value] of Object.entries(raw.timers || {})) {
      if (!['1', '2'].includes(id)) continue;
      if (!object(value) || !Number.isFinite(value.remaining) || value.remaining < 0 || value.remaining > 3600000 || !(value.end === null || Number.isFinite(value.end))) throw new Error('计时数据不正确');
      result.timers[id] = {remaining: value.remaining, end: value.end};
    }
    return result;
  }
  try { const saved = localStorage.getItem(KEY); if (saved) state = validate(JSON.parse(saved)); }
  catch (_) { storageOK = false; }
  function save() {
    try { localStorage.setItem(KEY, JSON.stringify(state)); storageOK = true; }
    catch (_) { storageOK = false; toast('浏览器未能保存记录，请到回顾页导出备份。'); }
  }
  if (!storageOK) toast('本机记录暂不可读取；页面仍可使用，请及时导出备份。');

  // Mobile navigation: keep focus out of the hidden panel, close on Escape or navigation.
  const menu = $('.menu-btn'), sidebar = $('#sidebar'), scrim = $('.scrim');
  function closeMenu() { sidebar.classList.remove('open'); scrim.classList.remove('open'); menu.setAttribute('aria-expanded', 'false'); menu.setAttribute('aria-label', '打开导航'); }
  menu?.addEventListener('click', () => { const open = !sidebar.classList.contains('open'); sidebar.classList.toggle('open', open); scrim.classList.toggle('open', open); menu.setAttribute('aria-expanded', String(open)); menu.setAttribute('aria-label', open ? '关闭导航' : '打开导航'); if (open) $('a', sidebar).focus(); });
  scrim?.addEventListener('click', closeMenu);
  $$('a', sidebar).forEach(a => a.addEventListener('click', closeMenu));
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape') { closeMenu(); menu?.focus(); }
    if (e.key === '/' && !/INPUT|TEXTAREA|SELECT/.test(document.activeElement?.tagName)) { e.preventDefault(); const input = $('#global-search') || $('#exercise-search'); if (input) input.focus(); else location.href = 'search.html'; }
  });
  for (const key of ['size', 'tone']) {
    const control = $(`#reading-${key}`); if (!control) continue;
    control.value = document.documentElement.dataset[key];
    control.addEventListener('change', () => {
      document.documentElement.dataset[key] = control.value;
      try { localStorage.setItem('probability-reading-v1', JSON.stringify({size: $('#reading-size').value, tone: $('#reading-tone').value})); } catch (_) { toast('阅读设置未能保存。'); }
    });
  }
  $('.print-btn')?.addEventListener('click', () => window.print());
  let printClosed = [];
  window.addEventListener('beforeprint', () => { printClosed = $$('details:not([open])'); printClosed.forEach(el => el.open = true); });
  window.addEventListener('afterprint', () => printClosed.forEach(el => el.open = false));

  // Plain text is never inserted as HTML. Only pre-rendered, tracked knowledge-card math is HTML.
  function el(tag, text, cls) { const n = document.createElement(tag); if (text !== undefined) n.textContent = text; if (cls) n.className = cls; return n; }
  function row(item) {
    const a = el('a', undefined, 'review-row'); a.href = item.url;
    const div = el('div'); div.append(el('strong', `${item.id} · ${item.title}`), el('small', `第 ${item.chapter} 章 · 点击继续练习`)); a.append(div, el('span', '→')); return a;
  }
  function updateProgress() {
    const count = Object.values(state.progress).filter(x => x === 'mastered').length;
    const target = $('#mastered-count'); if (target) { target.replaceChildren(document.createTextNode(count), el('span', '道练习')); }
    $$('[data-progress]').forEach(b => { const selected = state.progress[b.dataset.progress] === b.dataset.state; b.classList.toggle('selected', selected); b.setAttribute('aria-pressed', String(selected)); });
    $$('[data-badge]').forEach(b => { const s = state.progress[b.dataset.badge]; b.textContent = s === 'mastered' ? '已掌握' : s === 'review' ? '待复习' : '未标记'; b.className = `badge ${s || ''}`; });
    $$('[data-recall]').forEach(b => { const selected = !!state.recall[b.dataset.recall]; b.textContent = selected ? '✓ 已加入回顾' : '◇ 加入记忆回顾'; b.setAttribute('aria-pressed', String(selected)); b.classList.toggle('selected', selected); });
    $$('.progress-track[data-chapter]').forEach(track => {
      const id = +track.dataset.chapter, all = index.filter(x => x.chapter === id && x.kind === '原创练习');
      const done = all.filter(x => state.progress[x.id] === 'mastered').length;
      $('i', track).style.width = `${100 * done / all.length}%`;
      const label = $(`[data-chapter-label="${id}"]`); if (label) label.textContent = `已独立完成 ${done} / ${all.length} 题`;
    });
    for (const selector of ['#home-review', '#review-list']) {
      const root = $(selector); if (!root) continue; root.replaceChildren();
      const queue = index.filter(x => state.progress[x.id] === 'review');
      (selector === '#home-review' ? queue.slice(0, 4) : queue).forEach(x => root.append(row(x)));
      if (!queue.length) root.append(el('p', '还没有待复习的题。在练习下标记“需要复习”，下次从这里继续。', 'empty'));
    }
  }
  $$('[data-progress]').forEach(b => b.addEventListener('click', () => { const id = b.dataset.progress; if (state.progress[id] === b.dataset.state) delete state.progress[id]; else state.progress[id] = b.dataset.state; save(); updateProgress(); filterExercises(); toast('学习状态已更新'); }));
  $$('[data-recall]').forEach(b => b.addEventListener('click', () => { const id = b.dataset.recall; if (state.recall[id]) delete state.recall[id]; else state.recall[id] = {due: Date.now(), interval: 0}; save(); updateProgress(); toast(state.recall[id] ? '已加入记忆回顾，今天即可复习' : '已从回顾中移除'); }));
  $$('[data-note]').forEach(n => { n.value = state.notes[n.dataset.note] || ''; n.addEventListener('input', () => { state.notes[n.dataset.note] = n.value; save(); }); });

  function initGuide(guide) {
    const steps = $$('.guide-step', guide); let current = 0, all = false;
    function render() {
      steps.forEach((x, i) => x.hidden = !all && i !== current);
      $('.guide-count', guide).textContent = all ? `全部 ${steps.length} 步` : `第 ${current + 1} / ${steps.length} 步`;
      $('[data-guide="prev"]', guide).disabled = all || current === 0;
      $('[data-guide="next"]', guide).disabled = all || current === steps.length - 1;
      $('[data-guide="all"]', guide).textContent = all ? '恢复逐步引导' : '展开全部步骤';
    }
    $$('[data-guide]', guide).forEach(b => b.addEventListener('click', () => { if (b.dataset.guide === 'all') all = !all; else current += b.dataset.guide === 'next' ? 1 : -1; render(); }));
    guide.resetGuide = () => { current = 0; all = false; render(); };
  }
  $$('.guide').forEach(initGuide);
  $$('[data-reset-problem]').forEach(b => b.addEventListener('click', () => { const card = b.closest('.exercise'); $$('details', card).forEach(x => x.open = false); $('.guide', card)?.resetGuide(); toast('已收起提示和答案；你的草稿保留。'); }));

  function filterExercises() {
    const search = $('#exercise-search'); if (!search) return;
    const term = search.value.trim().toLowerCase(), ch = $('#chapter-filter').value, review = $('#review-filter').checked;
    let count = 0;
    $$('.exercise-row').forEach(r => { const show = (!term || r.dataset.search.toLowerCase().includes(term)) && (!ch || r.dataset.chapter === ch) && (!review || state.progress[r.dataset.id] === 'review'); r.hidden = !show; if (show) count++; });
    $('#filter-count').textContent = `显示 ${count} / ${$$('.exercise-row').length} 道练习`;
    $('#empty-filter').hidden = count > 0;
  }
  ['#exercise-search', '#chapter-filter', '#review-filter'].forEach(s => $(s)?.addEventListener('input', filterExercises));
  const globalSearch = $('#global-search');
  function search() {
    const term = globalSearch.value.trim().toLowerCase(), root = $('#search-results'); root.replaceChildren();
    if (!term) { $('#search-count').textContent = '输入关键词开始搜索。支持中文、英文术语与完整题号。'; return; }
    const matches = index.filter(x => `${x.id} ${x.title} ${x.en || ''} ${x.text}`.toLowerCase().includes(term));
    $('#search-count').textContent = `找到 ${matches.length} 条结果`;
    matches.forEach(x => { const a = el('a', undefined, 'search-result'); a.href = x.url; a.append(el('small', `${x.kind} · 第 ${x.chapter} 章 · ${x.id}`), el('h2', x.title), el('p', x.text.replace(/\$|\\[A-Za-z]+|[{}]/g, '').slice(0, 160))); root.append(a); });
    if (!matches.length) root.append(el('p', '没有找到结果。试试“条件概率”“正态”或题号 P1-01。', 'empty'));
  }
  if (globalSearch) { globalSearch.value = new URLSearchParams(location.search).get('q') || ''; globalSearch.addEventListener('input', search); search(); }

  function renderRecall() {
    const root = $('#recall-list'); if (!root) return; root.replaceChildren();
    const entries = Object.entries(state.recall).filter(([id]) => byId.has(id)).sort((a, b) => a[1].due - b[1].due);
    const due = entries.filter(([, v]) => v.due <= Date.now());
    $('#recall-count').textContent = `${entries.length} 张卡 · ${due.length} 张到期`;
    const shown = $('#due-only').checked ? due : entries;
    if (!shown.length) root.append(el('p', entries.length ? '今天的回顾已完成。取消“只看今天到期”可提前复习。' : '从知识卡下点击“加入记忆回顾”，建立自己的复习清单。', 'empty'));
    shown.forEach(([id, info]) => {
      const x = byId.get(id), card = el('article', undefined, 'card');
      card.append(el('p', `下次复习：${new Date(info.due).toLocaleDateString('zh-CN')} · ${x.en}`, 'card-meta'), el('h3', x.title), el('p', '先回想公式与适用条件，再展开核对。', 'recall-prompt'));
      const d = el('details'), summary = el('summary', '展开公式与条件'), body = el('div', undefined, 'prose'); body.innerHTML = x.answer; d.append(summary, body); card.append(d);
      const controls = el('div', undefined, 'recall-controls');
      [['again', '还不熟 · 10 分钟'], ['good', '记住了 · 1 天'], ['easy', '很熟悉 · 3 天']].forEach(([grade, label]) => {
        const b = el('button', label); b.addEventListener('click', () => { const days = grade === 'again' ? 10 / 1440 : grade === 'good' ? 1 : 3; state.recall[id] = {due: Date.now() + days * 86400000, interval: days}; save(); renderRecall(); toast('下次回顾时间已安排'); }); controls.append(b);
      });
      const remove = el('button', '移除'); remove.addEventListener('click', () => { delete state.recall[id]; save(); renderRecall(); });
      const link = el('a', '重新学习 ↗'); link.href = x.url; controls.append(remove, link); card.append(controls); root.append(card);
    });
  }
  $('#due-only')?.addEventListener('change', renderRecall);
  $('#export-records')?.addEventListener('click', () => { const url = URL.createObjectURL(new Blob([JSON.stringify({...state, exportedAt: new Date().toISOString()}, null, 2)], {type: 'application/json'})); const a = el('a'); a.href = url; a.download = `probability-study-${new Date().toISOString().slice(0, 10)}.json`; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000); toast('学习记录已导出'); });
  $('#import-records')?.addEventListener('change', async e => {
    const file = e.target.files[0]; if (!file) return;
    try { if (file.size > 5000000) throw new Error('文件超过 5 MB'); const imported = validate(JSON.parse(await file.text())); for (const k of ['notes', 'progress', 'recall', 'scores', 'timers']) Object.assign(state[k], imported[k]); save(); updateProgress(); renderRecall(); toast('学习记录已合并'); }
    catch (error) { toast(`未导入：${error.message}`); }
    e.target.value = '';
  });

  // Exam clock uses an absolute end time, so background tabs and reloads do not lose elapsed time.
  const exam = $('.exam-toolbar');
  if (exam) {
    const id = exam.dataset.exam, duration = +exam.dataset.minutes * 60000;
    if (!state.timers[id]) state.timers[id] = {remaining: duration, end: null};
    const timer = state.timers[id]; timer.remaining = Math.min(duration, timer.remaining);
    function renderTimer() {
      const remaining = timer.end === null ? timer.remaining : Math.max(0, timer.end - Date.now());
      if (timer.end !== null && remaining === 0) { timer.remaining = 0; timer.end = null; save(); toast('时间到了，可以停止作答并开始核对。'); }
      const sec = Math.ceil(remaining / 1000); $('.timer', exam).textContent = `${String(Math.floor(sec / 60)).padStart(2, '0')}:${String(sec % 60).padStart(2, '0')}`;
      $('[data-timer="toggle"]', exam).textContent = timer.end === null ? (remaining ? '开始 / 继续' : '已结束') : '暂停计时';
      $('[data-timer="toggle"]', exam).disabled = remaining === 0;
    }
    $('[data-timer="toggle"]', exam).addEventListener('click', () => { if (timer.end === null) timer.end = Date.now() + timer.remaining; else { timer.remaining = Math.max(0, timer.end - Date.now()); timer.end = null; } save(); renderTimer(); });
    $('[data-timer="reset"]', exam).addEventListener('click', () => { timer.remaining = duration; timer.end = null; save(); renderTimer(); toast('计时已重置；草稿与分数保留。'); });
    function score() { $('#exam-score').textContent = $$('[data-score]').reduce((sum, input) => sum + (+input.value || 0), 0); }
    $$('[data-score]').forEach(input => { input.value = state.scores[input.dataset.score] ?? ''; input.addEventListener('input', () => { const num = Math.max(0, Math.min(+input.max, Math.round(+input.value || 0))); if (input.value !== '') input.value = num; state.scores[input.dataset.score] = num; save(); score(); }); });
    score(); renderTimer(); setInterval(renderTimer, 500);
  }

  // Probability experiments, with deterministic numerical functions exposed only for testability.
  function normalCDF(x) {
    const a = Math.abs(x), t = 1 / (1 + 0.2316419 * a);
    const tail = Math.exp(-a * a / 2) / Math.sqrt(2 * Math.PI) * t * (0.319381530 + t * (-0.356563782 + t * (1.781477937 + t * (-1.821255978 + t * 1.330274429))));
    return x >= 0 ? 1 - tail : tail;
  }
  function cdf(type, x) { if (type === 'normal') return normalCDF(x); if (type === 'uniform') return Math.max(0, Math.min(1, x)); if (type === 'exponential') return x < 0 ? 0 : 1 - Math.exp(-x); return x < 0 ? 0 : x < 1 ? 0.25 : x < 2 ? 0.75 : 1; }
  function pdf(type, x) { if (type === 'normal') return Math.exp(-x * x / 2) / Math.sqrt(2 * Math.PI); if (type === 'uniform') return x >= 0 && x <= 1 ? 1 : 0; if (type === 'exponential') return x >= 0 ? Math.exp(-x) : 0; return x === 0 || x === 2 ? 0.25 : x === 1 ? 0.5 : 0; }
  const svgNS = 'http://www.w3.org/2000/svg';
  function svgNode(tag, attrs, text) { const node = document.createElementNS(svgNS, tag); Object.entries(attrs).forEach(([k, v]) => node.setAttribute(k, String(v))); if (text !== undefined) node.textContent = text; return node; }
  function bayes() {
    const p = +$('#prior').value / 100, sens = +$('#sensitivity').value / 100, fp = +$('#false-positive').value / 100;
    for (const id of ['prior', 'sensitivity', 'false-positive']) $(`#${id}-label`).textContent = `${+$('#' + id).value}%`;
    const tp = p * sens, falseP = (1 - p) * fp, posterior = tp / (tp + falseP);
    $('#bayes-result').textContent = `${(posterior * 100).toFixed(2)}%`;
    $('#bayes-equation').textContent = `${tp.toFixed(5)} ÷ (${tp.toFixed(5)} + ${falseP.toFixed(5)})`;
    $('#bayes-counts').textContent = `按 10,000 人的期望人数：真阳性 ${(tp * 10000).toFixed(1)} 人，假阳性 ${(falseP * 10000).toFixed(1)} 人。图中两段长度表示阳性人群内的比例。`;
    const chart = $('#bayes-chart'); chart.replaceChildren();
    chart.append(svgNode('text', {x: 28, y: 45}, '所有阳性结果 = 真阳性 + 假阳性'));
    chart.append(svgNode('rect', {x: 28, y: 80, width: 384 * posterior, height: 64, fill: '#39765a'}), svgNode('rect', {x: 28 + 384 * posterior, y: 80, width: 384 * (1 - posterior), height: 64, fill: '#d9b87f'}));
    chart.append(svgNode('rect', {x: 28, y: 178, width: 12, height: 12, fill: '#39765a'}), svgNode('text', {x: 47, y: 189}, `真阳性 ${(posterior * 100).toFixed(1)}%`), svgNode('rect', {x: 228, y: 178, width: 12, height: 12, fill: '#d9b87f'}), svgNode('text', {x: 247, y: 189}, `假阳性 ${((1 - posterior) * 100).toFixed(1)}%`));
  }
  function distribution(reset = false) {
    const type = $('#distribution').value, range = $('#threshold');
    const limits = type === 'normal' ? [-4, 4, 0, 0.45] : type === 'uniform' ? [-0.3, 1.3, 0.5, 1.15] : type === 'exponential' ? [-0.5, 5, 1, 1.15] : [-0.5, 2.5, 1, 0.6];
    const [lo, hi, initial, max] = limits;
    if (reset) { range.min = lo; range.max = hi; range.value = initial; }
    const x = +range.value; $('#threshold-label').textContent = x.toFixed(2); $('#cdf-result').textContent = cdf(type, x).toFixed(4);
    $('#density-result').textContent = type === 'discrete' ? `当前单点概率 P(X=x) = ${pdf(type, x).toFixed(2)}` : `当前密度 f(x) ≈ ${pdf(type, x).toFixed(4)}；单点概率为 0`;
    $('#distribution-help').textContent = type === 'discrete' ? 'X=0、1、2 的概率为 1/4、1/2、1/4。阈值刚好到达某个点时，该点概率立即计入 F(x)。' : type === 'normal' ? '正态密度的全体面积为 1。此处 F 使用数值近似；视窗外仍有少量尾部面积。' : type === 'uniform' ? '密度在 (0,1) 内为 1，区间外为 0。累计概率在两个端点之间线性增长。' : '密度从 1 开始衰减，但累计概率持续增长并趋近于 1。';
    const chart = $('#distribution-chart'); chart.replaceChildren();
    const X = v => 40 + (v - lo) / (hi - lo) * 370, Y = v => 220 - v / max * 175;
    for (let i = 0; i <= 4; i++) { const v = lo + i * (hi - lo) / 4; chart.append(svgNode('line', {x1: X(v), y1: 30, x2: X(v), y2: 220, stroke: '#e0e5da'}), svgNode('text', {x: X(v), y: 243, 'text-anchor': 'middle'}, v.toFixed(1))); }
    chart.append(svgNode('line', {x1: 40, y1: 220, x2: 415, y2: 220, stroke: '#91a38e'}));
    if (type === 'discrete') {
      [0, 1, 2].forEach(v => { chart.append(svgNode('rect', {x: X(v) - 16, y: Y(pdf(type, v)), width: 32, height: 220 - Y(pdf(type, v)), fill: v <= x ? '#39765a' : '#d4ddcf'}), svgNode('text', {x: X(v), y: Y(pdf(type, v)) - 9, 'text-anchor': 'middle'}, String(pdf(type, v)))); });
    } else {
      const points = Array.from({length: 401}, (_, i) => { const v = lo + i / 400 * (hi - lo); return [v, X(v), Y(pdf(type, v))]; });
      const shade = points.filter(v => v[0] <= x); shade.push([x, X(x), Y(pdf(type, x))]);
      chart.append(svgNode('path', {d: `M${X(lo)} 220 ${shade.map(v => `L${v[1]} ${v[2]}`).join(' ')} L${X(x)} 220 Z`, fill: '#bdd1b4'}));
      chart.append(svgNode('path', {d: points.map((v, i) => `${i ? 'L' : 'M'}${v[1]} ${v[2]}`).join(' '), fill: 'none', stroke: '#39765a', 'stroke-width': 2.5}));
    }
    chart.append(svgNode('line', {x1: X(x), y1: 25, x2: X(x), y2: 224, stroke: '#b37d35', 'stroke-width': 2, 'stroke-dasharray': '5 4'}), svgNode('text', {x: 42, y: 19}, type === 'discrete' ? '分布律 P(X=k)' : '概率密度 f(x)'));
  }
  if ($('#prior')) {
    ['prior', 'sensitivity', 'false-positive'].forEach(id => $('#' + id).addEventListener('input', bayes)); bayes();
    $('#distribution').addEventListener('change', () => distribution(true)); $('#threshold').addEventListener('input', () => distribution()); distribution(true);
    let heads = 0, total = 0, history = [];
    function coins() {
      $('#coin-total').textContent = total; $('#coin-heads').textContent = heads; $('#coin-rate').textContent = total ? (heads / total).toFixed(4) : '—';
      const chart = $('#coin-chart'); chart.replaceChildren();
      chart.append(svgNode('line', {x1: 45, y1: 125, x2: 775, y2: 125, stroke: '#b58a4b', 'stroke-dasharray': '6 4'}), svgNode('text', {x: 10, y: 129}, '0.5'), svgNode('text', {x: 45, y: 238}, '0'), svgNode('text', {x: 770, y: 238, 'text-anchor': 'end'}, String(total)));
      if (history.length) {
        const stride = Math.max(1, Math.floor(history.length / 800));
        const points = history.filter((_, i) => i % stride === 0 || i === history.length - 1);
        chart.append(svgNode('polyline', {points: points.map(v => `${45 + v.n / total * 730},${220 - v.rate * 190}`).join(' '), fill: 'none', stroke: '#39765a', 'stroke-width': 2}));
      }
    }
    $$('[data-toss]').forEach(b => b.addEventListener('click', () => { if (total >= 100000) { toast('本次已模拟 100,000 次，可重新开始。'); return; } const count = Math.min(+b.dataset.toss, 100000 - total); for (let i = 0; i < count; i++) { total++; heads += Math.random() < 0.5 ? 1 : 0; history.push({n: total, rate: heads / total}); } coins(); }));
    $('#coin-reset').addEventListener('click', () => { heads = total = 0; history = []; coins(); }); coins();
  }
  window.ProbabilityMath = Object.freeze({normalCDF, cdf, pdf});
  updateProgress(); filterExercises(); renderRecall();
})();
