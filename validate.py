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
assert [len(c['sections']) for c in course]==[6,5,5,5,2,3,8,8,6,3,6,3,3,4]
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
assert len(pages)==40, len(pages)
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
# Independently check the new numerical comparisons and normal quantile examples.
exact_tail=1-sum(math.comb(200,k)*0.01**k*0.99**(200-k) for k in range(2))
assert math.isclose(exact_tail,0.5953543153,abs_tol=1e-10)
exact_cdf=sum(math.comb(500,k)*0.004**k*0.996**(500-k) for k in range(2))
assert math.isclose(exact_cdf,0.4054634230,abs_tol=1e-10)
assert math.isclose(abs(exact_cdf-3*math.exp(-2)),0.0005424267,abs_tol=1e-10)
assert math.isclose((1+math.erf(1.96/math.sqrt(2)))/2,0.975,abs_tol=3e-6)
# Direct finite-n binomial probabilities approach the stated fixed-k Poisson limit.
for k in (0,1,2,5):
    target=math.exp(-2)*2**k/math.factorial(k)
    error=[]
    for n in (100,1000,10000):
        p=2/n
        value=math.comb(n,k)*p**k*(1-p)**(n-k)
        error.append(abs(value-target))
    assert error[2]<error[1]<error[0], (k,error)
assert 'poisson-limit' in pages['chapter-2.html'].ids
# New chapters: independently compute representative examples by enumeration,
# regression normal equations and numerical integration.
from itertools import product
from statistics import mean, variance
sample=[1,3,5,7]
boot_means=[mean(xs) for xs in product(sample,repeat=4)]
assert math.isclose(mean((m-mean(sample))**2 for m in boot_means),1.25)
xs=[0,1,2];ys=[1,2,2]
sxx=sum((x-mean(xs))**2 for x in xs)
sxy=sum((x-mean(xs))*(y-mean(ys)) for x,y in zip(xs,ys))
b=sxy/sxx;a=mean(ys)-b*mean(xs)
residuals=[y-a-b*x for x,y in zip(xs,ys)]
assert math.isclose(a,7/6) and math.isclose(b,.5)
assert math.isclose(sum(r*r for r in residuals),1/6)
assert abs(sum(residuals))<1e-12 and abs(sum(x*r for x,r in zip(xs,residuals)))<1e-12
assert math.isclose(variance([1,-1,1,1,2]),1.2)
assert math.isclose(mean([1,-1,1,1,2])/math.sqrt(1.2/5),1.632993161855452)
groups=[[1,2,3],[4,5,6]];grand=mean(sum(groups,[]))
between=sum(len(g)*(mean(g)-grand)**2 for g in groups)
within=sum((x-mean(g))**2 for g in groups for x in g)
assert math.isclose(between,13.5) and math.isclose(within,4)
assert math.isclose(between+within,sum((x-grand)**2 for g in groups for x in g))
transition=[[.8,.2],[.4,.6]]
squared=[[sum(transition[i][k]*transition[k][j] for k in range(2)) for j in range(2)] for i in range(2)]
assert all(math.isclose(a,b) for a,b in zip(squared[0],[.72,.28]))
stationary=[2/3,1/3]
assert all(math.isclose(sum(stationary[i]*transition[i][j] for i in range(2)),stationary[j]) for j in range(2))
# Fourier transform of R(t)=3 exp(-2|t|): even cosine integral.
for omega in [0,1,3]:
    dt=20/20000
    numerical=2*sum(3*math.exp(-2*(i+.5)*dt)*math.cos(omega*(i+.5)*dt)*dt for i in range(20000))
    assert math.isclose(numerical,12/(4+omega**2),abs_tol=2e-6)
# Confirm code fences remain code rather than being interpreted as mathematics.
r_page=(ROOT/'chapter-11.html').read_text(encoding='utf-8')
assert r_page.count('<pre><code class="language-r">')==6
assert 'boxplot.stats(x)$stats' in r_page
assert 'CODETOKEN' not in r_page
print(f'PASS: {len(pages)} pages, {links} local links/anchors, {sum(x.math for x in pages.values())} rendered formulas; {len(concepts)} concepts, {len(exercises)} exercises, 2 x 100-point exams; mathematical spot checks.')
