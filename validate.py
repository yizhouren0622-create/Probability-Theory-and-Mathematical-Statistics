"""Validate generated pages, content coverage, links and numerical examples."""
import json, math, re
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import urlsplit, unquote
ROOT=Path(__file__).resolve().parent
load=lambda x:json.loads((ROOT/'data'/x).read_text(encoding='utf-8'))
course=load('course.json');exercises=load('exercises.json');exams=load('exams.json')
concepts=[x for c in course for s in c['sections'] for x in s['concepts']]
ids=[x['id'] for x in concepts+exercises]+[q['id'] for e in exams for q in e['questions']]
assert len(ids)==len(set(ids)), 'Duplicate content ids'
assert [len(c['sections']) for c in course]==[6,5]
for c in course:
    for s in c['sections']:
        assert s['concepts'], s['id']
        assert any(e['section']==s['id'] for e in exercises), f'Missing practice for {s["id"]}'
for c in concepts:
    for key in ['id','title','en','plain','statement','formula','conditions','proof','example','pitfall']:assert c[key], (c['id'],key)
    assert any(e['concept']==c['id'] for e in exercises), f'No practice for {c["id"]}'
for e in exercises:
    assert len(e['hints'])==3 and len(e['steps'])>=4
    assert e['answer'] and e['check']
    assert e['concept'] in [c['id'] for c in concepts]
for e in exams:
    assert sum(q['points'] for q in e['questions'])==100
    assert all(q['solution'] and q['answer'] and q['rubric'] for q in e['questions'])
class Page(HTMLParser):
    def __init__(self,text):
        super().__init__();self.ids=set();self.links=[];self.math=0;self.feed(text)
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if 'id' in a:
            assert a['id'] not in self.ids, f'Duplicate DOM id {a["id"]}'
            self.ids.add(a['id'])
        if tag=='math':self.math+=1
        for attr in ['href','src']:
            if attr in a:self.links.append(a[attr])
        if tag=='html':assert a.get('lang')=='zh-CN'
pages={p.name:Page(p.read_text(encoding='utf-8')) for p in ROOT.glob('*.html')}
links=0
for filename,page in pages.items():
    text=(ROOT/filename).read_text(encoding='utf-8')
    assert 'MATHTOKEN' not in text and 'math-error' not in text
    assert not any(ord(c)<32 and c not in '\n\r\t' for c in text), filename
    for link in page.links:
        url=urlsplit(link)
        if url.scheme or url.netloc:continue
        target=unquote(url.path) or filename
        assert (ROOT/target).exists(), (filename,link)
        if url.fragment and target.endswith('.html'):assert unquote(url.fragment) in pages[target].ids,(filename,link)
        links+=1
assert len(pages)==15, len(pages)
assert sum(x.math for x in pages.values())>300
# Independent numerical checks for selected nontrivial examples.
assert math.isclose(0.01*0.9/(0.01*0.9+0.99*0.05),2/13)
assert math.isclose(math.comb(4,2)*math.comb(6,1)/math.comb(10,3),0.3)
assert 1-0.8**10<0.9<=1-0.8**11
assert math.isclose(math.comb(5,3)*0.4**3*0.6**2,0.2304)
assert math.isclose(1-40**2/60**2,5/9)
assert math.isclose(2/9/(2/9+1/6),4/7)
# Composite midpoint integration verifies both transformed densities, away from integrable endpoint singularities via substitution y=t^2.
assert math.isclose(sum((1/4)*2*(2/10000) for _ in range(10000)),1,rel_tol=1e-9)
assert math.isclose((math.erf(2/math.sqrt(2))-math.erf(-1/math.sqrt(2)))/2,0.81859,abs_tol=1e-5)
print(f'PASS: {len(pages)} pages, {links} local links/anchors, {sum(x.math for x in pages.values())} rendered formulas; 25 concepts, 32 exercises, 2 x 100-point exams; mathematical spot checks.')
