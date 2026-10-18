"""Build offline-ready static pages. Run with Python 3.11+ and requirements-build.txt."""
import json, re, html, hashlib
from pathlib import Path
import markdown
from latex2mathml.converter import convert

ROOT=Path(__file__).resolve().parent
read=lambda name:json.loads((ROOT/'data'/name).read_text(encoding='utf-8'))
chapters=read('course.json'); exercises=read('exercises.json'); exams=read('exams.json'); audit=read('source-audit.json'); r_check=read('r-verification.json')
concepts=[dict(x,chapter=c['id'],section=s['id']) for c in chapters for s in c['sections'] for x in s['concepts']]
# Git checkouts and Windows editors may use different text line endings.
# Fingerprint canonical LF bytes so committed pages match a Linux CI rebuild.
asset_version=hashlib.sha256(b''.join((ROOT/p).read_bytes().replace(b'\r\n',b'\n') for p in ['build.py','assets/site.css','assets/site.js','data/course.json','data/exercises.json','data/exams.json','data/source-audit.json','data/r-verification.json'])).hexdigest()[:12]
esc=lambda s:html.escape(str(s),quote=True)
def md(text):
    tokens=[]
    code=[]
    def protect_code(m):
        code.append(m.group(0))
        return f'CODETOKEN{len(code)-1}END'
    text=re.sub(r'```[^\n]*\n.*?```|`[^`\n]+`',protect_code,text,flags=re.S)
    def render(m):
        block=m.group(1) is not None
        formula=m.group(1) if block else m.group(2)
        math=convert(formula,display='block' if block else 'inline')
        token=f'MATHTOKEN{len(tokens)}END'
        tokens.append(f'<div class="equation" tabindex="0">{math}</div>' if block else f'<span class="inline-math">{math}</span>')
        return token
    text=re.sub(r'\$\$(.*?)\$\$|(?<!\\)\$([^$\n]+?)(?<!\\)\$',render,text,flags=re.S)
    for i,t in enumerate(code):text=text.replace(f'CODETOKEN{i}END',t)
    text=markdown.markdown(text,extensions=['tables','sane_lists','fenced_code'])
    for i,t in enumerate(tokens):
        key=f'MATHTOKEN{i}END'
        if t.startswith('<div'):text=text.replace('<p>'+key+'</p>',t)
        text=text.replace(key,t)
    return text
def detail(title,body):return f'<details><summary>{esc(title)}</summary><div class="detail-body">{md(body)}</div></details>'

def r_result(ident):
    record=r_check['examples'].get(ident)
    if not record:return ''
    rows='\n'.join(f'{key} = {value:.8g}' for key,value in record['metrics'].items())
    body='```text\n'+rows+'\n```\n以上为实际执行后提取的数值，显示时保留约 8 位有效数字。 [运行版本与验证范围](sources.html#r-runtime)。'
    plot=r_check.get('graphics',{}).get(ident)
    if plot:
        body+=f'\n\n[![{plot["alt"]}]({plot["path"]})]({plot["path"]})\n\n{plot["caption"]} 图形由上方代码实际生成，已核对；点击图片可放大。'
    return detail(f'查看实际 R 运行结果 · {r_check["runDate"]}',body)
def heading(kicker,title,sub):return f'<div class="page-heading"><p class="eyebrow">{kicker}</p><h1>{title}</h1><p class="subtitle">{sub}</p></div>'
nav=[('index.html','学习总览','◈'),('beginner.html','从这里开始','↗'),('chapters.html','知识点与推导','∑'),('exercises.html','分步练习','⌘'),('labs.html','概率实验室','◉'),('formulas.html','公式速查','ƒ'),('exams.html','模拟考场','◷'),('memory.html','记忆与回顾','◇'),('sources.html','资料与版本','↗')]
def page(name,title,content,active=None):
    active=active or name
    links=''.join(f'<a href="{u}"'+(' class="active" aria-current="page"' if active==u else '')+f'><span aria-hidden="true">{icon}</span>{t}</a>' for u,t,icon in nav)
    chnav=''
    for label,lo,hi in [('概率论',1,5),('数理统计',6,11),('随机过程',12,14)]:
        links_ch=''.join(f'<a href="chapter-{c["id"]}.html"><span>{c["id"]:02}</span>{c["title"]}</a>' for c in chapters if lo<=c['id']<=hi)
        current=next((c['id'] for c in chapters if name in [f'chapter-{c["id"]}.html',f'practice-{c["id"]}.html']),0)
        chnav+=f'<details class="nav-group"'+(' open' if lo<=current<=hi else '')+f'><summary>{label} · {lo}–{hi} 章</summary>{links_ch}</details>'
    output=f'''<!doctype html><html lang="zh-CN" data-size="comfortable" data-tone="high"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="theme-color" content="#215d49"><meta name="description" content="按浙大盛骤第六版全书目录组织的概率论复习：白话讲解、公式推导、原创分步练习、模拟卷与交互实验。"><title>{title} · 概率论复习</title><link rel="icon" href="assets/icon.svg" type="image/svg+xml"><link rel="stylesheet" href="assets/site.css"><script src="assets/preferences.js"></script></head><body>
<a class="skip" href="#main">跳到正文</a><button class="scrim" aria-label="关闭导航" tabindex="-1"></button><aside class="sidebar" id="sidebar"><a class="brand" href="index.html"><span class="brand-icon">P</span><span>概率论与数理统计<small>理解 · 推理 · 掌握</small></span></a><p class="nav-label">学习工作台</p><nav aria-label="主要导航">{links}</nav><p class="nav-label">当前学习范围</p><nav aria-label="教材章节">{chnav}</nav><div class="sidebar-foot"><i></i>全书 14 章 · 可离线阅读<small>浙江大学 · 盛骤等编著</small></div></aside>
<div class="workspace"><header class="topbar"><button class="menu-btn" aria-label="打开导航" aria-controls="sidebar" aria-expanded="false">☰</button><div class="breadcrumb"><span class="parent">概率论复习 / </span>{title}</div><div class="top-actions"><a class="search-link" href="search.html" aria-label="搜索知识点与练习">⌕ <span>搜索知识点与练习</span><kbd>/</kbd></a><button class="print-btn">打印</button></div></header><main id="main">{content}<div class="reading" aria-label="阅读设置"><label>字号 <select id="reading-size"><option value="comfortable">舒适 · 22px</option><option value="large">大字 · 26px</option><option value="largest">特大 · 30px</option></select></label><label>配色 <select id="reading-tone"><option value="high">清晰绿白</option><option value="soft">柔和护眼</option></select></label><span>设置与学习记录自动保存在当前浏览器</span></div></main><footer>按第六版官方目录组织 · 知识讲解与训练题独立编写 · <a href="sources.html">来源与核对范围</a><span>全书 14 章持续审校。学习记录仅存本机，请定期导出备份。</span></footer></div><div id="toast" role="status" aria-live="polite"></div><script src="assets/index-data.js"></script><script src="assets/site.js" defer></script></body></html>'''
    for asset in ['site.css','site.js','index-data.js','preferences.js']:
        output=output.replace(f'assets/{asset}"',f'assets/{asset}?v={asset_version}"')
    (ROOT/name).write_text(output,encoding='utf-8')
def note(ident):return f'<label class="scratch-label" for="note-{ident}">先写下你的思路 <small>· 自动保存</small></label><textarea class="scratch" id="note-{ident}" data-note="{ident}" rows="2" placeholder="先列事件、判断模型，或写出关键的第一步……"></textarea>'
def progress(ident):return f'<div class="actions"><button data-progress="{ident}" data-state="review" aria-pressed="false">↻ 需要复习</button><button data-progress="{ident}" data-state="mastered" aria-pressed="false">✓ 已能独立完成</button><a href="#{ident}">题目直达链接 ↗</a></div>'

# Home
h=heading('PROBABILITY & STATISTICS / STUDY NOTES','让不确定的事，变得有章可循。','从随机事件到统计推断与随机过程，把概念想清楚，把每一步算明白。')
h+='''<section class="hero"><div class="hero-copy"><p class="eyebrow">全书 14 章 · 概率、统计与随机过程</p><h2>先理解概率，<br>再掌握解题。</h2><p>从白话解释出发，沿着推导理解公式。<br>先自己试一试，需要时再展开下一步。</p><div class="hero-buttons"><a class="primary" href="beginner.html">从这里开始 <span>→</span></a><a href="exercises.html">直接进入练习 ↗</a></div></div><div class="hero-art" aria-hidden="true"><span class="art-badge">每一块面积，都是一种可能。</span><svg viewBox="0 0 380 220"><defs><pattern id="grid" width="30" height="30" patternUnits="userSpaceOnUse"><path d="M 30 0 L 0 0 0 30" fill="none" stroke="#dce4d5" stroke-width=".6"/></pattern><linearGradient id="area" x1="0" y1="0" x2="0" y2="1"><stop stop-color="#599475" stop-opacity=".65"/><stop offset="1" stop-color="#b7ceb0" stop-opacity=".25"/></linearGradient></defs><rect x="15" y="5" width="350" height="190" fill="url(#grid)"/><path d="M30 178 C70 177 96 165 120 134 S161 45 190 43 S238 114 263 146 S315 177 350 178 L350 181 L30 181 Z" fill="url(#area)"/><path d="M30 178 C70 177 96 165 120 134 S161 45 190 43 S238 114 263 146 S315 177 350 178" fill="none" stroke="#326a50" stroke-width="2.8"/><path d="M24 181 H358 M190 26 V190" stroke="#8eab91" stroke-width="1"/><path d="M120 134 V181 M263 146 V181" stroke="#be8b45" stroke-dasharray="4 4"/><circle cx="190" cy="43" r="4" fill="#b58a4b"/><text x="180" y="207" fill="#41624e" font-size="14" font-family="Georgia">μ</text><text x="114" y="205" fill="#8b6c36" font-size="13" font-family="Georgia">a</text><text x="259" y="205" fill="#8b6c36" font-size="13" font-family="Georgia">b</text><text x="284" y="64" fill="#54725a" font-size="16" font-family="Georgia">P(a &lt; X ≤ b)</text></svg><span class="art-bottom">看见分布，也理解它背后的含义。</span></div></section>'''
h+=f'<section class="stats" aria-label="学习统计"><div><small>当前开放</small><strong>{len(chapters):02}<span>章 / {sum(len(c["sections"]) for c in chapters)} 节</span></strong></div><div><small>知识与推导</small><strong>{len(concepts)}<span>张知识卡</span></strong></div><div><small>原创分步训练</small><strong>{len(exercises)}<span>道练习</span></strong></div><div><small>我已独立完成</small><strong id="mastered-count">0<span>道练习</span></strong></div></section>'
h+='<div class="section-title"><div><p class="eyebrow">THE LEARNING MAP</p><h2>沿着教材，搭好知识骨架。</h2></div><a href="formulas.html">打开公式速查 →</a></div><section class="chapter-grid">'
for c in chapters:
    n=sum(x['chapter']==c['id'] for x in exercises)
    h+=f'<a class="chapter-card" href="chapter-{c["id"]}.html"><div class="card-top"><span class="chapter-number">{c["id"]:02}</span><span>{len(c["sections"])} 节 · {n} 道原创练习</span></div><h3>{c["title"]}</h3><p>{c["summary"]}</p><div class="progress-track" data-chapter="{c["id"]}"><i></i></div><div class="chapter-bottom"><span data-chapter-label="{c["id"]}">尚未标记完成</span><span>开始学习 ↗</span></div></a>'
h+='</section><section class="study-route"><div><b>01 / UNDERSTAND</b><h3>用自己的话说清楚</h3><p>先读直觉，再看使用条件，尝试复述公式。</p></div><div><b>02 / PRACTICE</b><h3>给思考留一点空白</h3><p>写下第一步，卡住时只展开一条提示。</p></div><div><b>03 / RECALL</b><h3>把不熟悉的留给明天</h3><p>标记待复习，再用限时模拟卷检验掌握。</p></div></section><div class="section-title"><h2>留给下一次的题</h2><a href="memory.html">打开回顾清单 →</a></div><div id="home-review"></div>'
page('index.html','学习总览',h)

# Full-book learning map
h=heading('THE WHOLE BOOK / 14 CHAPTERS','概率、统计与随机过程，一张完整的学习地图。','按第六版官方目录组织；每节提供知识卡与原创分步练习。正文逐页核对仍在进行。')
for label,lo,hi,intro in [('概率论基础',1,5,'从事件、分布到数字特征与极限定理，建立描述随机现象的语言。'),('数理统计',6,11,'从样本走向总体：估计、检验、回归、bootstrap 与 R 实践。'),('随机过程',12,14,'从单个随机变量走向随时间演化的随机系统。')]:
    h+=f'<section class="study-section"><h2>{label}</h2><p class="subtitle">{intro}</p><div class="chapter-grid">'
    for c in chapters:
        if not lo<=c['id']<=hi:continue
        h+=f'<article class="chapter-card"><div class="card-top"><span class="chapter-number">{c["id"]:02}</span><span>{len(c["sections"])} 节 · {sum(len(t["concepts"]) for t in c["sections"])} 张卡</span></div><h3><a href="chapter-{c["id"]}.html">{c["title"]} ↗</a></h3><p>{c["summary"]}</p><ul class="map-sections">'+''.join(f'<li><a href="chapter-{c["id"]}.html#section-{t["id"]}">{t["id"]} {t["title"]}</a></li>' for t in c['sections'])+f'</ul><a href="practice-{c["id"]}.html">本章分步练习 →</a></article>'
    h+='</div></section>'
page('chapters.html','全书知识地图',h)

# Concepts
for c in chapters:
    h=heading(f'CHAPTER {c["id"]:02} / CONCEPTS',c['title'],c['summary']+' 每张卡包含解释、条件、推导、例题与易错点。')
    h+='<nav class="chapter-selector" aria-label="知识点章节切换"><a href="chapters.html">← 全书知识地图</a><label for="chapter-jump">切换章节</label><select id="chapter-jump">'+''.join(f'<option value="chapter-{other["id"]}.html"'+(' selected' if other['id']==c['id'] else '')+f'>第 {other["id"]} 章 · {other["title"]}</option>' for other in chapters)+'</select></nav>'
    h+='<nav class="toc" aria-label="本章目录">'+''.join(f'<a href="#section-{s["id"]}">{s["id"]} {s["title"]}</a>' for s in c['sections'])+'</nav>'
    reviewed=all(t['id'] in audit['sections'] for t in c['sections'])
    scope='本章已按第六版官方样章逐页阅读，并核对正文知识主题；教材例题和习题未逐题复现。' if reviewed else '已补充术语、性质与证明；本章指定教材正文的逐页核对仍待完成。'
    h+=f'<p class="notice">{scope}<a href="sources.html#coverage">查看逐节内容清单、页码与核对状态</a>。</p><div class="actions proof-controls"><button data-proofs="open">展开本章全部证明</button><button data-proofs="close">收起本章全部证明</button></div>'
    if c['id']==11:
        plots_note='箱线图和残差图提供已核对的生成结果。' if len(r_check.get('graphics',{}))==2 else '图形外观核对另见运行记录。'
        h+=f'<p class="notice" id="r-execution">本章 6 段基础 R 示例已于 {esc(r_check["runDate"])} 在 WebR 0.6.0 / R 4.6.0 中执行，数值检查通过。每张卡可展开实际输出；{plots_note}<a href="sources.html#r-runtime">查看运行版本与验证范围</a>。</p>'
    for s in c['sections']:
        h+=f'<section class="study-section" id="section-{s["id"]}"><p class="eyebrow">SECTION {s["id"]}</p><h2>{s["title"]}</h2>'
        if s['id'] in audit['sections']:
            record=audit['sections'][s['id']]; source=audit['sources'][record['source']]
            h+=f'<p class="subtitle">正文主题已核对 · 第{source["edition"]}版第 {record["pages"][0]}–{record["pages"][1]} 页 · <a href="sources.html#audit-{s["id"]}">核对明细</a></p>'
        h+=f'<nav class="topic-index" aria-label="第 {s["id"]} 节知识点">'+''.join(f'<a href="#{x["id"]}">{x["title"]}</a>' for x in s['concepts'])+'</nav>'
        for x in s['concepts']:
            related=[e for e in exercises if e['concept']==x['id']]
            execution=r_result(x['id'])
            h+=f'<article class="card concept" id="{x["id"]}"><div class="card-meta">{s["id"]}<span>{x["en"]}</span><span class="tag">理解后再记忆</span></div><h3>{x["title"]}</h3><div class="plain"><strong>先用一句话理解</strong>{md(x["plain"])}</div>{md(x["statement"])}{md("$$"+x["formula"]+"$$")}<div class="conditions"><strong>使用条件</strong>{md(x["conditions"])}</div>{detail(x.get("proofTitle","展开性质证明 / 推导过程"),x["proof"])}{execution}{detail("做一道简单例题",x["example"])}<div class="pitfall"><strong>容易出错的地方</strong>{md(x["pitfall"])}</div><div class="actions"><button data-recall="{x["id"]}" aria-pressed="false">◇ 加入记忆回顾</button>'+(''.join(f'<a href="practice-{e["chapter"]}.html#{e["id"]}">试一题：{e["id"]} →</a>' for e in related[:1]))+'</div></article>'
        h+='</section>'
    h+=f'<div class="chapter-next"><a class="primary" href="practice-{c["id"]}.html">练习这一章 →</a>'
    following=next((other for other in chapters if other['id']>c['id']),None)
    if following:h+=f'<a class="secondary" href="chapter-{following["id"]}.html">进入第 {following["id"]} 章：{following["title"]} →</a>'
    if c['id']>1:h+=f'<a class="secondary" href="chapter-{c["id"]-1}.html">← 上一章</a>'
    h+='</div>'
    page(f'chapter-{c["id"]}.html',c['title'],h,'chapters.html')

# Exercises
def exercise_card(e):
    ident=e['id']
    guide=f'<details class="guide"><summary>带我一步一步做</summary><p class="guide-count">第 <span>1</span> / {len(e["steps"])} 步</p><ol class="guide-steps">'+''.join(f'<li class="guide-step"'+(' hidden' if i else '')+f'>{md(s)}</li>' for i,s in enumerate(e['steps']))+'</ol><div class="guide-controls"><button data-guide="prev" disabled>上一步</button><button data-guide="next">下一步</button><button data-guide="all">展开全部步骤</button></div></details>'
    hints='<details><summary>给我一点提示</summary><div class="detail-body">'+''.join(detail(f'提示 {i+1}',s) for i,s in enumerate(e['hints']))+'</div></details>'
    solution='\n\n'.join(f'{i+1}. {s}' for i,s in enumerate(e['steps']))+'\n\n**答案**\n\n'+e['answer']+'\n\n**检验与提醒**\n\n'+e['check']
    return f'<article class="card exercise" id="{ident}"><div class="card-meta"><span class="tag">原创 {ident}</span><span>第 {e["section"]} 节 · {e["level"]}</span></div><h3>{e["title"]}</h3>{md(e["question"])}{note(ident)}{hints}{guide}{detail("查看完整解答与检验",solution)}{progress(ident)}<div class="actions"><button data-reset-problem>收起提示，重新做</button><a href="chapter-{e["chapter"]}.html#{e["concept"]}">补习对应知识点 ↗</a></div></article>'
for c in chapters:
    es=[e for e in exercises if e['chapter']==c['id']]
    h=heading(f'PRACTICE / CHAPTER {c["id"]:02}',c['title']+' · 分步练习',f'{len(es)} 道原创训练 · 三级提示 · 逐步引导 · 草稿自动保存')
    h+='<p class="notice">P 开头的编号是本站原创练习编号，不对应教材课后题。先独立尝试，再按需展开提示。</p><nav class="toc" aria-label="练习题号">'+''.join(f'<a href="#{e["id"]}">{e["id"]}</a>' for e in es)+'</nav>'+''.join(exercise_card(e) for e in es)
    page(f'practice-{c["id"]}.html','第'+str(c['id'])+'章练习',h,'exercises.html')
h=heading('PRACTICE LIBRARY','每一道题，都知道从哪里入手。','按知识点找到题目，从独立尝试到分步引导。所有题目均为原创训练。')
h+='<div class="filter-bar"><label for="exercise-search">查找</label><input id="exercise-search" type="search" placeholder="题号、关键词，例如 贝叶斯、P2-08"><label for="chapter-filter">章节</label><select id="chapter-filter"><option value="">全部章节</option>'+''.join(f'<option value="{c["id"]}">第 {c["id"]} 章</option>' for c in chapters)+'</select><label><input type="checkbox" id="review-filter"> 只看待复习</label></div><p class="filter-count" id="filter-count" aria-live="polite"></p><div id="exercise-index">'
for e in exercises:
    topic=next(x for x in concepts if x['id']==e['concept'])
    searchtext=e['id']+' '+e['title']+' '+e['question']+' '+topic['title']+' '+topic['en']
    h+=f'<a class="exercise-row" data-id="{e["id"]}" data-chapter="{e["chapter"]}" data-search="{esc(searchtext)}" href="practice-{e["chapter"]}.html#{e["id"]}"><span class="row-number">{e["id"]}</span><div><strong>{e["title"]}</strong><small>第 {e["section"]} 节 · {e["level"]} · 3 条提示 / {len(e["steps"])} 步引导</small></div><span class="badge" data-badge="{e["id"]}">未标记</span></a>'
h+='</div><p id="empty-filter" class="empty" hidden>没有匹配的题目。试试更短的关键词，或取消筛选。</p>'
page('exercises.html','分步练习',h)

# Beginner path
h=heading('START SMALL / BUILD INTUITION','先认清问题，再选择公式。','基础薄弱也没关系。从下面的符号与四个问题开始。')
h+='<section class="card prose"><h2>一张题目，先问自己四件事</h2><ol class="steps-route"><li><strong>一次试验到底做什么？</strong><br>写清有无放回、顺序是否重要、是否固定次数。</li><li><strong>问题中的“且、或、已知”是什么事件？</strong><br>把自然语言翻译为交、并、补和条件概率。</li><li><strong>可用哪条模型假设？</strong><br>等可能、独立、均匀、正态都要有依据，不能由“随机”自行推出。</li><li><strong>结果是否合理？</strong><br>概率在 0 到 1 之间；分布律总和与密度积分均为 1。</li></ol></section>'
symbols=[('事件',r'$A\cup B$ / $A\cap B$','A 或 B / A 且 B（交集有时简记 AB）'),('条件',r'$P(A\mid B)$','已知 B 发生，A 发生的概率'),('组合',r'$\binom nk$','从 n 个不同对象中不计顺序地选 k 个'),('分布律',r'$P(X=x)$','离散变量在 x 处的概率'),('累计',r'$F(x)=P(X\le x)$','截至 x（包含 x）的全部概率'),('密度',r'$f(x)$','概率堆积的高度；区间概率用积分')]
h+='<section class="card prose"><h2>符号小词典</h2><div class="table-wrap"><table class="formula-table"><thead><tr><th>主题</th><th>写法</th><th>怎样读</th></tr></thead><tbody>'+''.join(f'<tr><td>{a}</td><td>{md(b)}</td><td>{c}</td></tr>' for a,b,c in symbols)+'</tbody></table></div></section>'
h+='<section class="card prose"><h2>三个先修小练习</h2>'+detail('组合数：为什么从 5 个选 2 个是 10？',r'先按顺序选有 $5\cdot4=20$ 种。但每一对被按两个顺序数了两遍，所以 $\binom52=20/2=10$。检验：直接列 12、13、14、15、23、24、25、34、35、45。')+detail('积分：如何算区间下方的面积？',r'试算 $\int_0^1 2x\,dx$。原函数为 $x^2$，代上限再减下限，得 $1^2-0^2=1$。把上限换成 t，面积为 $t^2$（$0\le t\le1$），这也是一个分布函数的内部表达式。')+detail('解不等式：平方如何反解？',r'当 $y\ge0$，$x^2\le y$ 等价于 $-\sqrt y\le x\le\sqrt y$，不是只有 $x\le\sqrt y$。如果已知 x 非负，才可以只保留 $0\le x\le\sqrt y$。')+'</section>'
h+='<section class="card prose"><h2>建议的两轮复习</h2><p>第一轮按章阅读知识卡，展开例题后合上重做。第二轮只看公式的适用条件，独立完成练习，把卡住的题标记为“需要复习”。完成后做模拟卷，按评分要点给自己评分。</p><div class="actions"><a class="primary" href="chapter-1.html">开始第一章 →</a><a class="secondary" href="labs.html">先做一个概率实验</a></div></section>'
page('beginner.html','从这里开始',h)

# Formula reference
h=heading('FORMULA DESK','公式要记，条件也要一起记。','按章节整理的公式与适用条件。点击标题可返回完整推导。')
h+='<nav class="toc" aria-label="公式章节">'+''.join(f'<a href="#formula-chapter-{c["id"]}">{c["id"]}. {c["title"]}</a>' for c in chapters)+'</nav>'
for c in chapters:
    h+=f'<section class="card" id="formula-chapter-{c["id"]}"><h2>{c["id"]:02} · {c["title"]}</h2>'
    for x in [x for x in concepts if x['chapter']==c['id']]:
        h+=f'<div class="prose"><h3><a href="chapter-{c["id"]}.html#{x["id"]}">{x["title"]} ↗</a></h3>{md("$$"+x["formula"]+"$$")}<p class="muted">{esc(x["conditions"])}</p></div><hr style="border:0;border-top:1px solid var(--line);margin:25px 0">'
    h+='</section>'
# Render conditions' inline mathematics rather than exposing LaTeX.
h=re.sub(r'<p class="muted">(.*?)</p>',lambda m:'<div class="muted">'+md(html.unescape(m.group(1)))+'</div>',h,flags=re.S)
page('formulas.html','公式速查',h)

# Exams
h=heading('MOCK EXAMS','把学过的，放进一张试卷。',f'当前提供 {len(exams)} 套原创自测卷 · 每套 100 分 · 计时、草稿与自评分数保存在本机')
for e in exams:
    h+=f'<section class="card exam-cover"><p class="eyebrow">PAPER {e["id"]:02}</p><h2>{e["title"]}</h2><p class="muted">{e["scope"]}</p><div class="exam-meta"><span>{e["minutes"]} 分钟</span><span>100 分</span><span>{len(e["questions"])} 道题</span></div><a class="primary" href="exam-{e["id"]}.html">进入模拟考场 →</a></section>'
page('exams.html','模拟考场',h)
for e in exams:
    h=heading(f'PAPER {e["id"]:02} / SELF ASSESSMENT',e['title'],f'{e["minutes"]} 分钟 · 100 分 · 先独立作答，再展开解析与评分要点。')
    h+=f'<div class="exam-toolbar" data-exam="{e["id"]}" data-minutes="{e["minutes"]}"><span class="timer" aria-label="剩余时间">{e["minutes"]}:00</span><button data-timer="toggle">开始计时</button><button data-timer="reset">重置计时</button><span class="exam-score">我的自评分 <strong id="exam-score">0</strong> / 100</span></div><p class="notice">倒计时到零会提醒，但不会删除草稿或锁定答案。暂停后停止计时；运行中关闭页面，重新打开仍按实际经过时间继续。</p>'
    for q in e['questions']:
        solution=detail('完成后再看：解答与评分',q['solution']+'\n\n**答案**\n\n'+q['answer']+'\n\n**评分要点**\n\n'+q['rubric'])
        h+=f'<article class="card exercise" id="{q["id"]}"><div class="card-meta"><span class="tag">{q["id"]}</span><span>{q["points"]} 分</span></div><h3>{q["title"]}</h3>{md(q["question"])}{note(q["id"])}{solution}<label class="score-control">本题自评 <input type="number" min="0" max="{q["points"]}" step="1" data-score="{q["id"]}" aria-label="{q["id"]} 自评分"> / {q["points"]} 分</label></article>'
    page(f'exam-{e["id"]}.html',e['title'],h,'exams.html')

# Review & search
h=heading('RECALL & REVIEW','把“看懂了”，变成“记得住”。','先尝试回忆，再展开知识卡。用掌握程度安排下一次复习。')
h+='<div class="record-tools"><button id="export-records">导出学习记录</button><label class="file-label">导入记录<input id="import-records" type="file" accept="application/json,.json"></label></div><p class="notice">记录包括草稿、掌握状态、知识卡回顾与模拟卷进度。只保存在当前浏览器，换设备前请导出；导入会合并记录，同名项目以导入文件为准。</p><div class="section-title"><h2>知识卡回顾</h2><span class="muted" id="recall-count"></span></div><label class="muted"><input type="checkbox" id="due-only" checked> 只看今天到期</label><div id="recall-list" style="margin-top:20px"></div><div class="section-title"><h2>待复习的题</h2><a href="exercises.html">全部练习 →</a></div><div id="review-list"></div>'
page('memory.html','记忆与回顾',h)
h=heading('FIND YOUR NEXT STEP','把问题带来，把线索找回去。','搜索知识点、英文术语、原创题号和题目关键词。')
h+='<div class="filter-bar"><label for="global-search">搜索</label><input id="global-search" type="search" placeholder="例如：Bayes、密度、P2-15" autocomplete="off"></div><p class="filter-count" id="search-count" aria-live="polite"></p><div id="search-results"></div>'
page('search.html','搜索',h,'')

# Labs
h=heading('PROBABILITY LAB','动一动参数，看看概率怎么变。','三个小实验，把抽象公式变成看得见的过程。数值演示辅助理解，不代替证明。')
h+='''<section class="card"><div class="card-meta"><span class="tag">01 / 条件概率</span></div><h2>阳性之后，概率有多大？</h2><p class="muted">这是一个教学用检测模型。观察先验比例怎样改变贝叶斯后验。</p><div class="lab-grid"><div class="lab-controls"><label for="prior">先验患病比例 <output id="prior-label">1%</output><input id="prior" type="range" min="0.1" max="50" step="0.1" value="1"></label><label for="sensitivity">灵敏度 <output id="sensitivity-label">90%</output><input id="sensitivity" type="range" min="1" max="100" step="1" value="90"></label><label for="false-positive">假阳性率 <output id="false-positive-label">5%</output><input id="false-positive" type="range" min="0" max="50" step="0.1" value="5"></label><div class="lab-result" aria-live="polite">阳性后患病的概率<strong id="bayes-result"></strong><span id="bayes-equation"></span></div></div><div><svg class="chart" id="bayes-chart" viewBox="0 0 440 250" role="img" aria-label="阳性结果中真阳性与假阳性的比例"></svg><p class="chart-caption" id="bayes-counts"></p><a href="chapter-1.html#bayes">回到贝叶斯公式 →</a></div></div></section>'''
h+='''<section class="card"><div class="card-meta"><span class="tag">02 / 分布探索</span></div><h2>从密度到累计概率</h2><div class="lab-grid"><div class="lab-controls"><label for="distribution">选择分布</label><select id="distribution"><option value="normal">标准正态 N(0,1)</option><option value="uniform">均匀 U(0,1)</option><option value="exponential">指数 Exp(1)</option><option value="discrete">离散：0、1、2</option></select><label for="threshold">移动阈值 x <output id="threshold-label">0.00</output><input id="threshold" type="range" min="-4" max="4" step="0.01" value="0"></label><div class="lab-result" aria-live="polite">F(x) = P(X ≤ x)<strong id="cdf-result"></strong><span id="density-result"></span></div><p class="chart-caption" id="distribution-help"></p></div><div><svg class="chart" id="distribution-chart" viewBox="0 0 440 270" role="img" aria-label="分布与阈值左侧的概率区域"></svg><p class="chart-caption">阴影面积（离散分布为选中柱的概率之和）对应 F(x)。图形按当前视窗绘制，数值使用完整分布计算。</p><a href="chapter-2.html#cdf">回到分布函数 →</a></div></div></section>'''
h+='''<section class="card"><div class="card-meta"><span class="tag">03 / 重复试验</span></div><h2>抛硬币：频率怎样变化？</h2><p class="muted">公平硬币模型，每次独立。使用浏览器伪随机数模拟；长期趋稳不代表每一步都更接近 1/2。</p><div class="actions"><button data-toss="1">抛 1 次</button><button data-toss="100">抛 100 次</button><button data-toss="1000">抛 1000 次</button><button id="coin-reset">重新开始</button></div><div class="coin-stats" style="margin:23px 0"><div>总次数<strong id="coin-total">0</strong></div><div>正面次数<strong id="coin-heads">0</strong></div><div>正面频率<strong id="coin-rate">—</strong></div></div><svg class="chart" id="coin-chart" viewBox="0 0 800 250" role="img" aria-label="正面频率随模拟次数变化的折线"></svg><p class="chart-caption">虚线是模型概率 0.5。刷新页面会重新开始本次实验，不影响学习记录。</p></section>'''
page('labs.html','概率实验室',h)

# Sources
h=heading('SOURCES & SCOPE','知道内容从哪里来，也知道它的边界。','教材版本、逐节内容清单与核对状态。')
h+=f'<section class="card prose"><h2>教材与版本</h2><p>目标教材为浙江大学盛骤、谢式千、潘承毅编《概率论与数理统计》第六版，高等教育出版社，ISBN 9787040666892。已核对出版社公开的全部 14 章、{sum(len(c["sections"]) for c in chapters)} 节目录，包括标星选学节。</p><p><strong>第三章已逐页阅读官方第六版样章，按正文知识主题核对；全书其余章节的指定教材正文核对仍未完成。</strong>尚未取得全书可合法完整读取的正文，不能声称全书逐页核对完毕或全部知识点无遗漏。用户提供的第五版内层压缩包加密，未读取正文。</p></section>'
h+=f'<section class="card prose"><h2>当前内容</h2><p>{len(concepts)} 张知识卡、{len(exercises)} 道原创分步练习，覆盖全书每一节；另提供 {len(exams)} 套模拟卷、{sum(len(e["questions"]) for e in exams)} 道自测题，以及 3 个交互实验。每章均有一套原创自测卷。</p><p>知识卡区分定义、模型假设、证明和算法解释，配有条件、例子和易错点。P 开头是本站原创题号，不对应教材习题。旧链接和学习记录编号继续有效。第十一章 6 段基础 R 代码已实际执行并核对数值；<a href="sources.html#r-runtime">版本与验证范围另列</a>。</p><p>全书内容为独立编写的复习资料。第三章的正文主题与样章逐节对照，教材例题、各节练习和章末习题未逐题复现或提供全解；其他章节继续按可读取正文审校并记录版本与页码。</p></section>'
for front in audit.get('frontMatterChecks',[]):
    h+=f'<section class="card prose" id="{esc(front["id"])}"><h2>前言与版本修订核对</h2><p>{esc(front["date"])}：{esc(front["title"])}。{esc(front["scope"])}</p><p><a href="{esc(front["url"])}">出版社公开前言 ↗</a></p></section>'
h+='''<section class="card prose"><h2>可核实的来源</h2><ul class="sources-list"><li><a href="https://xuanshu.hep.com.cn/front/book/findBookDetails?bookId=6967ccf2e119ac97292654e8">高等教育出版社：第六版图书介绍、全书目录与官方试读入口</a>。已读取完整目录；官方试读为第三章，不能作为全书审校依据。</li><li><a href="https://xuanshu.hep.com.cn/front/h5Mobile/bookDetails?bookId=5c9a64e9f18f967ee7f3805c">高等教育出版社：第五版图书信息</a>。用于版本与目录对照。</li><li><a href="https://stat.ethz.ch/R-manual/R-devel/library/stats/html/00Index.html">R 官方 stats 文档</a>：统计函数定义与参数。</li><li><a href="https://stat.ethz.ch/R-manual/R-devel/library/boot/html/00Index.html">R 官方 boot 文档</a>：自助抽样与置信区间的使用说明。</li><li><a href="https://www.itl.nist.gov/div898/handbook/">NIST/SEMATECH 统计方法手册</a>：统计推断与试验分析的辅助参考。</li><li><a href="https://yizhouren0622-create.github.io/math-physics-review/">数学物理方法复习网站</a>：学习流程与布局参考。</li></ul></section>'''
h+='<section class="card prose"><h2>第二章专项交叉核对</h2><p><a href="https://iaer.dufe.edu.cn/file/eeefaf43-8ff3-11ee-9d7b-005056a49984/概率论与数理统计教案.pdf">东北财经大学《概率论与数理统计》教案</a>采用盛骤等第五版作为教材，第二章列出几何分布、超几何分布及泊松定理等教学要点。本站据此补充两个分布的独立编写讲解与练习；教案不是第六版教材正文，不能据此宣称第六版已逐页核对。</p></section>'
for review in audit.get('externalChecks',[]):
    context_link=f' · <a href="{esc(review["contextUrl"])}">课程教材说明</a>' if review.get('contextUrl') else ''
    location='PDF 页码 '+ '、'.join(map(str,review['pdfPages'])) if review.get('pdfPages') else '网页段落：'+'；'.join(review['webSections'])
    h+=f'<section class="card prose"><h2>{esc(review["title"])}</h2><p>{esc(review["date"])} · {esc(location)}。{esc(review["scope"])} <a href="{esc(review["url"])}">公开资料</a>{context_link}。</p><ul>'
    for ident in review['concepts']:
        topic=next(x for x in concepts if x['id']==ident)
        h+=f'<li><a href="chapter-{topic["chapter"]}.html#{ident}">{esc(topic["title"])}</a></li>'
    h+='</ul></section>'
h+='<section class="card prose"><h2>第四章拓展参考</h2><p><a href="https://ocw.mit.edu/courses/res-6-012-introduction-to-probability-spring-2018/d973b10c2587781f86ca4f2aff49098f_MITRES_6_012S18_Textbook.pdf">MIT OpenCourseWare《Introduction to Probability》公开摘要</a>列出全期望与全方差公式。本站据此独立编写离散分组下的定义、证明和练习；该资料不是盛骤教材，不能作为指定版本的正文核对记录。</p></section>'
h+='<section class="card prose"><h2>第五章拓展参考</h2><p><a href="https://ocw.mit.edu/courses/res-6-012-introduction-to-probability-spring-2018/d973b10c2587781f86ca4f2aff49098f_MITRES_6_012S18_Textbook.pdf">MIT OpenCourseWare《Introduction to Probability》公开摘要</a>列有马尔可夫不等式、切比雪夫不等式及二项分布的正态近似；<a href="https://ocw.mit.edu/courses/18-655-mathematical-statistics-spring-2016/6c41b4096a836ff41f8de46cf54b5b7c_MIT18_655S16_LecNote15.pdf">MIT《Mathematical Statistics》极限定理讲义</a>列有棣莫弗—拉普拉斯定理和连续性修正。本站据此交叉核对公式并独立编写说明、证明和练习；另对照 <a href="https://ocw.mit.edu/courses/6-436j-fundamentals-of-probability-fall-2018/f44fa78f05ac31a4ba2bd82f599dcf60_MIT6_436JF18_lec17.pdf">MIT 6.436J 极限定理讲义</a>及<a href="https://ocw.mit.edu/courses/18-440-probability-and-random-variables-spring-2014/a88fddfed579f8c6af51949301f86e18_MIT18_440S14_Lecture31.pdf">MIT 18.440 CLT 讲义</a>，补全辛钦截断证明与特征函数工具定义。分析前置定理的引用单独说明。它们不是盛骤教材正文。</p></section>'
h+='<section class="card prose"><h2>第六章抽样分布参考</h2><p><a href="https://ocw.mit.edu/courses/18-443-statistics-for-applications-spring-2015/06daf6d78e7eb0465d6bb53e8f96b2ff_MIT18_443S15_LEC11.pdf">MIT OpenCourseWare 次序统计量讲义</a>与<a href="https://www.itl.nist.gov/div898/handbook/eda/section3/eda3666.htm">NIST 卡方分布说明</a>用于交叉核对排序样本的分布、卡方密度与数字特征。<a href="https://www.itl.nist.gov/div898/handbook/eda/section3/eda3664.htm">NIST t 分布说明</a>及<a href="https://www.itl.nist.gov/div898/handbook/eda/section3/eda3665.htm">F 分布说明</a>用于核对密度、尾部与矩的存在条件。本站独立编写推导、平方关系证明和练习；它们不是盛骤指定教材正文。</p></section>'
h+='<section class="card prose"><h2>第七章拓展参考</h2><p><a href="https://ocw.mit.edu/courses/9-07-statistics-for-brain-and-cognitive-science-fall-2016/beb2665d692b4c4da1a4156cc8e6a393_MIT9_07F16_lec9.pdf">MIT OpenCourseWare《Likelihood Theory I &amp; II》讲义</a>用于交叉核对费舍尔信息和 Cramér–Rao 下界及其正则条件；<a href="https://www.itl.nist.gov/div898/handbook/eda/section3/eda358.htm">NIST 正态样本方差卡方分布说明</a>辅助核对样本方差的抽样分布。本站独立编写证明、数值例题与练习；费舍尔信息卡标为拓展，并未核对为盛骤第六版正文内容。另参考该 MIT 似然讲义中的正态模型、<a href="https://www.itl.nist.gov/div898/handbook/eda/section3/eda366h.htm">NIST Beta 分布定义</a>与<a href="https://www.ocw.mit.edu/courses/18-05-introduction-to-probability-and-statistics-spring-2014/f5cffb9eb5ca110cd92133292fc2a5a6_MIT18_05S14_Reading15a.pdf">MIT Beta/正态共轭先验讲义</a>，独立补充正态 MLE 全局最大证明、Beta 的矩和正态后验更新。</p></section>'
h+='<section class="card prose"><h2>第八章推导参考</h2><p><a href="https://www.itl.nist.gov/div898/handbook/eda/section3/eda35f.htm">NIST 卡方拟合检验说明</a>与<a href="https://online.stat.psu.edu/stat504/Lesson02">宾州州立大学《Binomial and Multinomial Inference》公开课程</a>用于交叉核对 Pearson 统计量、自由度及参数估计的条件。本站独立编写给定类别概率时的多项中心极限定理与投影证明，以及原创练习；这些外部资料不构成盛骤第六版教材正文核对。</p></section>'
h+='<section class="card prose"><h2>第九章推导参考</h2><p><a href="https://www.itl.nist.gov/div898/handbook/prc/section4/prc426.htm">NIST 单因素方差分析的对比说明</a>用于交叉核对对比、标准误与误差自由度；<a href="https://ocw.mit.edu/courses/15-075j-statistical-thinking-and-data-analysis-fall-2011/ddc78dd2737c4a68130e976afb7b1f5f_MIT15_075JF11_chpt10.pdf">MIT OpenCourseWare 一元回归讲义</a>与<a href="https://online.stat.psu.edu/stat501/Lesson01">宾州州立大学回归课程</a>用于交叉核对回归平方和、R² 与单斜率的 t/F 关系。本站独立编写证明和练习；这些资料不是盛骤指定教材正文。</p></section>'
h+='<section class="card prose"><h2>第十章区间推导参考</h2><p><a href="https://ocw.mit.edu/courses/18-05-introduction-to-probability-and-statistics-spring-2022/mit18_05_s22_class24-prep.pdf">MIT OpenCourseWare bootstrap 置信区间讲义</a>与<a href="https://ocw.mit.edu/courses/18-443-statistics-for-applications-spring-2015/a5bffcc1d9a00836a5b83346318cef19_MIT18_443S15_LEC6.pdf">MIT 18.443 估计误差反解讲义</a>用于交叉核对百分位区间与基本区间的定义及端点顺序。本站独立编写证明和练习；这些外部资料不是盛骤指定教材正文。</p></section>'
h+=f'<section class="card prose" id="r-runtime"><h2>第十一章 R 示例运行记录</h2><p>{esc(r_check["runDate"])}：逐段执行本站 6 段基础 R 示例，数值检查通过。运行环境为 WebR 0.6.0，{esc(r_check["rVersion"])}，平台 {esc(r_check["platform"])}；随机数设置为 {esc(r_check["rng"])}。随机示例保留代码中的 set.seed(2026)，bootstrap 使用 B=2000 和 quantile 默认 type=7。</p><p>实际输出与确定性统计量的手算值交叉核对；bootstrap 模拟标准差与其条件方差 1.25 对照。数值检查的图形调用使用 pdf(NULL)；另有 {len(r_check.get("graphics",{}))} 幅图通过 R PDF 设备实际导出，转为 PNG 后逐图核对，显示在对应代码卡中。注释中的 boot::boot 包调用未执行。本记录验证本站代码，不构成第十一章指定教材正文审校。</p><p>依据与复核：<a href="https://docs.r-wasm.org/webr/v0.6.0/downloading.html">WebR 官方运行说明</a>、<a href="https://stat.ethz.ch/R-manual/R-devel/library/stats/html/t.test.html">R t.test</a>、<a href="https://stat.ethz.ch/R-manual/R-devel/library/stats/html/predict.lm.html">predict.lm</a>及<a href="https://stat.ethz.ch/R-manual/R-devel/library/stats/html/quantile.html">quantile 官方文档</a>。<a href="data/r-verification.json">完整数值与代码版本记录</a>。</p></section>'
h+='<section class="card prose"><h2>第十二章泊松过程参考</h2><p><a href="https://ocw.mit.edu/courses/6-262-discrete-stochastic-processes-spring-2011/9f76a2356ac8abdd15a8d06c151f723b_MIT6_262S11_lec05.pdf">MIT OpenCourseWare《Poisson Combining and Splitting》讲义</a>用于交叉核对条件到达、分流与合并性质。本站独立编写条件二项分布、概率母函数证明和练习；另对照 <a href="https://ocw.mit.edu/courses/6-262-discrete-stochastic-processes-spring-2011/68c1d4b947f61d7374154a8902ed2c10_MIT6_262S11_lec04.pdf">MIT 6.262 泊松过程基础讲义</a>，独立编写小区间刻画、到达时刻与计数对偶、Erlang 密度及间隔独立性的推导。该资料不是盛骤第六版教材正文。</p></section>'
h+='<section class="card prose"><h2>第十三章马尔可夫链参考</h2><p><a href="https://ocw.mit.edu/courses/6-438-algorithms-for-inference-fall-2014/e193ad751ae309992372b55e70b8a080_MIT6_438F14_Lec18.pdf">MIT OpenCourseWare 细致平衡讲义</a>用于核对可逆性及其推出平稳分布的条件；<a href="https://live.ocw.mit.edu/courses/res-6-012-introduction-to-probability-spring-2018/d973b10c2587781f86ca4f2aff49098f_MITRES_6_012S18_Textbook.pdf">MIT 概率教材公开摘要的吸收时间小节</a>用于核对一步分析方程。本站独立编写基本矩阵推导、反例和练习；<a href="https://www.ocw.mit.edu/courses/18-175-theory-of-probability-spring-2014/10958ec4974f4b29bb1b10709570c6b7_MIT18_175S14_Lecture31.pdf">MIT 18.175 马尔可夫链讲义</a>用于交叉检查返回、常返与访问次数的解释；本站独立给出首次返回更新方程与级数判据证明。这些资料不是盛骤第六版教材正文。</p></section>'
h+='<section class="card prose"><h2>第十四章平稳序列参考</h2><p><a href="https://online.stat.psu.edu/stat510/Lesson01">宾州州立大学 AR(1) 平稳性与自相关课程</a>、<a href="https://online.stat.psu.edu/stat510/Lesson02">AR(1) 因果级数课程</a>及<a href="https://online.stat.psu.edu/stat510/Lesson12">谱分析课程</a>用于交叉核对离散时间 AR(1) 的方差、相关与频率约定。本站独立编写证明和练习；这些资料不是盛骤指定教材正文。</p></section>'
h+='<section class="card prose" id="coverage"><h2>逐节内容清单与核对状态</h2><p><strong>目录：已核实。讲解与练习：已编写。指定教材正文逐页核对：未完成。</strong>以下列出实际写入的知识卡。数学验证包含公式渲染、若干数值交叉检验及推导检查，不表示已穷尽所有定理和教材例题。</p>'
for source in audit['sources'].values():
    h+=f'<p><strong>{esc(source["title"])}</strong>：{esc(source["readDate"])} 阅读，共 {source["samplePages"]} 页，印刷页码 {source["printedPages"][0]}–{source["printedPages"][1]}。{esc(source["scope"])} <a href="{esc(source["url"])}">出版社试读入口 ↗</a></p>'
for c in chapters:
    h+=f'<details><summary>第 {c["id"]} 章 · {c["title"]}</summary><div class="detail-body">'
    for t in c['sections']:
        h+=f'<h4 id="audit-{t["id"]}">{t["id"]} {t["title"]}</h4>'
        if t['id'] in audit['sections']:
            record=audit['sections'][t['id']];source=audit['sources'][record['source']]
            h+=f'<p><strong>正文主题已核对</strong>：第{source["edition"]}版第 {record["pages"][0]}–{record["pages"][1]} 页。{esc(record["changes"])}</p><p>核对主题：'+esc('；'.join(record['topics']))+'。</p>'
        else:h+='<p>指定教材正文：待核对。以下为独立编写的讲解与练习。</p>'
        h+='<ul>'+''.join(f'<li><a href="chapter-{c["id"]}.html#{x["id"]}">{x["title"]}</a></li>' for x in t['concepts'])+'</ul>'
    h+='</div></details>'
h+='</section><section class="card prose"><h2>修订记录</h2><p>2026-10-13：创建并扩充前两章，补充泊松定理及二项分布的泊松近似、关键术语和性质证明。2026-10-14：按用户要求扩展至全书，增加章节地图和章节切换，保留旧锚点、题号与学习记录。</p><p>如发现遗漏或错误，请在 <a href="https://github.com/yizhouren0622-create/Probability-Theory-and-Mathematical-Statistics/issues">仓库 Issues</a> 提供章节、知识卡或题号以及修正依据。</p></section>'
page('sources.html','资料与版本',h)

# Browser data: plain-text search plus pre-rendered math for recall.
index=[]
for x in concepts:
    index.append(dict(id=x['id'],kind='知识卡',title=x['title'],en=x['en'],text=' '.join(x[k] for k in ['plain','statement','conditions','proof','example','pitfall']),url=f'chapter-{x["chapter"]}.html#{x["id"]}',chapter=x['chapter'],answer=md('$$'+x['formula']+'$$')+md(x['conditions'])))
for e in exercises:
    topic=next(x for x in concepts if x['id']==e['concept'])
    index.append(dict(id=e['id'],kind='原创练习',title=e['title'],text=e['question'],en=topic['title']+' '+topic['en'],url=f'practice-{e["chapter"]}.html#{e["id"]}',chapter=e['chapter']))
for e in exams:
    for q in e['questions']:index.append(dict(id=q['id'],kind='模拟卷',title=q['title'],text=q['question'],url=f'exam-{e["id"]}.html#{q["id"]}',chapter=e['id'],points=q['points'],examId=e['id'],examMinutes=e['minutes']))
(ROOT/'assets/index-data.js').write_text('window.STUDY_INDEX='+json.dumps(index,ensure_ascii=False).replace('</','<\\/')+';\n',encoding='utf-8')
print(f'Built {len(list(ROOT.glob("*.html")))} pages, {len(concepts)} concepts, {len(exercises)} exercises, {sum(len(e["questions"]) for e in exams)} exam questions.')
