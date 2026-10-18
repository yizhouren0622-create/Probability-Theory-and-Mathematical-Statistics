"""Validate generated pages, content coverage, links and numerical examples."""
import json, math, re, hashlib
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import urlsplit, unquote
ROOT=Path(__file__).resolve().parent
load=lambda x:json.loads((ROOT/'data'/x).read_text(encoding='utf-8'))
course=load('course.json');exercises=load('exercises.json');exams=load('exams.json');audit=load('source-audit.json')
concepts=[x for c in course for s in c['sections'] for x in s['concepts']]
# Execution claims must correspond to the exact currently displayed R code.
r_check=load('r-verification.json')
r_examples={x['id']:re.findall(r'```r\n(.*?)\n```',x['statement'],re.S) for x in concepts if x['id'].startswith('r-')}
assert len(r_examples)==6 and r_examples.keys()==r_check['examples'].keys()
for ident,blocks in r_examples.items():
    assert len(blocks)==1 and r_check['examples'][ident]['status']=='executed_and_checked'
    assert hashlib.sha256(blocks[0].encode()).hexdigest()==r_check['examples'][ident]['codeSha256'], f'Rerun changed R example: {ident}'
for ident,plot in r_check.get('graphics',{}).items():
    assert plot['status']=='visually_reviewed' and plot['alt'] and plot['caption']
    assert plot['codeSha256']==r_check['examples'][ident]['codeSha256']
    assert hashlib.sha256((ROOT/plot['path']).read_bytes()).hexdigest()==plot['sha256'], f'Review changed R plot: {ident}'
for review in audit.get('externalChecks',[]):
    assert review['date'] and review['scope'] and (review.get('pdfPages') or review.get('webSections'))
    assert all(any(c['id']==cid for c in concepts) for cid in review['concepts'])
for front in audit.get('frontMatterChecks',[]):
    assert front['date'] and front['scope'] and front['url'] and front['edition'] in (5,6)
    assert front['readPreviewPages'] and len(set(front['readPreviewPages']))==len(front['readPreviewPages'])
    assert all(isinstance(p,int) and 1<=p<=front['previewPages'] for p in front['readPreviewPages'])
ids=[x['id'] for x in concepts+exercises]+[q['id'] for e in exams for q in e['questions']]
assert len(ids)==len(set(ids)), 'Duplicate content ids'
assert [len(c['sections']) for c in course]==[6,5,5,5,2,3,8,8,6,3,6,3,3,4]
section_ids={s['id'] for c in course for s in c['sections']}
for sid,record in audit['sections'].items():
    assert sid in section_ids and record['status']=='body_topics_reviewed'
    source=audit['sources'][record['source']]
    assert source['printedPages'][0]<=record['pages'][0]<=record['pages'][1]<=source['printedPages'][1]
    assert source['samplePages']==source['printedPages'][1]-source['printedPages'][0]+1
    assert source['edition'] in (5,6) and source['readDate'] and record['topics']
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
    assert e['minutes']>0 and isinstance(e['minutes'],int)
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
# A failed partial build must not pass by validating a mixture of old and new
# pages. Check every page's canonical input fingerprint and the search IDs.
build_inputs=['build.py','assets/site.css','assets/site.js','data/course.json',
              'data/exercises.json','data/exams.json','data/source-audit.json','data/r-verification.json']
expected_version=hashlib.sha256(b''.join((ROOT/p).read_bytes().replace(b'\r\n',b'\n') for p in build_inputs)).hexdigest()[:12]
index_text=(ROOT/'assets/index-data.js').read_text(encoding='utf-8')
index_entries=json.loads(index_text.removeprefix('window.STUDY_INDEX=').strip().removesuffix(';'))
assert {x['id'] for x in index_entries}==set(ids), 'Search index is stale; run a successful full build'
links=0
for filename,page in pages.items():
    text=(ROOT/filename).read_text(encoding='utf-8')
    for asset in ['site.css','site.js','index-data.js','preferences.js']:
        assert f'assets/{asset}?v={expected_version}' in text, f'Stale generated page: {filename}'
    assert 'MATHTOKEN' not in text and 'math-error' not in text
    assert not any(ord(c)<32 and c not in '\n\r\t' for c in text), filename
    for link in page.links:
        url=urlsplit(link)
        if url.scheme or url.netloc:continue
        target=unquote(url.path) or filename
        assert (ROOT/target).exists(), (filename,link)
        if url.fragment and target.endswith('.html'):assert unquote(url.fragment) in pages[target].ids,(filename,link)
        links+=1
assert len(pages)==38+len(exams), len(pages)
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
# Enumerate the new waiting-time and without-replacement exercises independently.
assert math.isclose((3/4)**4/4,81/1024)
assert math.isclose(((3/4)**4/4)/((3/4)**3),3/16)
from itertools import combinations
hyper_counts=[sum(i<4 for i in picked) for picked in combinations(range(12),3)]
assert len(hyper_counts)==220
assert math.isclose(sum(k>=1 for k in hyper_counts)/len(hyper_counts),41/55)
assert math.isclose(sum(hyper_counts)/len(hyper_counts),1)
assert math.isclose(sum((k-1)**2 for k in hyper_counts)/len(hyper_counts),6/11)
# Uniform area in the triangular support 0<x<y<1.
midpoints=[(i+.5)/10000 for i in range(10000)]
assert math.isclose(sum(2*(1-x) for x in midpoints)/10000,1,abs_tol=1e-10)
assert math.isclose(sum(2*(1-2*x) for x in midpoints if x<.5)/10000,.5,abs_tol=1e-10)
# Enumerate a two-group Bernoulli mixture directly, then verify the variance split.
mixture=[(.5,.2),(.5,.8)]
mu=sum(weight*p for weight,p in mixture)
within=sum(weight*p*(1-p) for weight,p in mixture)
between=sum(weight*(p-mu)**2 for weight,p in mixture)
direct=sum(weight*(p*(1-mu)**2+(1-p)*mu**2) for weight,p in mixture)
assert math.isclose(mu,.5) and math.isclose(within,.16)
assert math.isclose(between,.09) and math.isclose(direct,within+between)
# Chapter 7: independently check the normal-variance MSE example and the
# Bernoulli information bound used in the new guided exercises.
true_variance=4
n_variance=5
sigma_fourth=true_variance**2
q_mean=(n_variance-1)*true_variance
q_var=2*(n_variance-1)*sigma_fourth
s2_mse=q_var/(n_variance-1)**2
t_bias=q_mean/n_variance-true_variance
t_var=q_var/n_variance**2
t_mse=t_var+t_bias**2
assert math.isclose(s2_mse,8) and math.isclose(t_bias,-.8)
assert math.isclose(t_var,5.12) and math.isclose(t_mse,5.76)
assert math.isclose(s2_mse-t_mse,(3*n_variance-1)*sigma_fourth/(n_variance**2*(n_variance-1)))
for p in (.1,.3,.8):
    n_bern=20
    fisher=n_bern/(p*(1-p))
    bernoulli_mean_var=p*(1-p)/n_bern
    assert math.isclose(1/fisher,bernoulli_mean_var)
assert 'normal-variance-mse' in pages['chapter-7.html'].ids
assert 'fisher-cramer-rao' in pages['chapter-7.html'].ids
assert all(x in pages['practice-7.html'].ids for x in ('P7-10','P7-11'))

# Chapter 8: independently check the grouped multinomial example and the
# rank-(k-1) projection behind Pearson's limiting degrees of freedom.
probs=[1/2,1/3,1/6]
counts=[27,23,10]
expected=[60*p for p in probs]
assert sum(counts)==sum(expected)==60
pearson=sum((o-e)**2/e for o,e in zip(counts,expected))
assert math.isclose(pearson,.75)
assert math.isclose(math.exp(-pearson/2),.6872892787909722)
q=[math.sqrt(p) for p in probs]
projection=[[float(i==j)-q[i]*q[j] for j in range(3)] for i in range(3)]
assert math.isclose(sum(projection[i][i] for i in range(3)),2)
assert all(math.isclose(sum(projection[i][k]*projection[k][j] for k in range(3)),projection[i][j]) for i in range(3) for j in range(3))
assert 'pearson-df-proof' in pages['chapter-8.html'].ids
assert 'P8-10' in pages['practice-8.html'].ids

# Chapter 9: recompute a planned contrast and the regression ANOVA identity
# from raw observations, including the distinction between contrast t² and
# the overall three-group F statistic.
contrast_groups=[[1,2,3],[4,5,6],[2,3,4]]
contrast_means=[sum(g)/len(g) for g in contrast_groups]
contrast_coeff=[-.5,1,-.5]
contrast_estimate=sum(c*m for c,m in zip(contrast_coeff,contrast_means))
anova_sse=sum((y-m)**2 for g,m in zip(contrast_groups,contrast_means) for y in g)
anova_mse=anova_sse/(9-3)
contrast_se2=anova_mse*sum(c*c/len(g) for c,g in zip(contrast_coeff,contrast_groups))
grand_mean=sum(map(sum,contrast_groups))/9
anova_ssb=sum(len(g)*(m-grand_mean)**2 for g,m in zip(contrast_groups,contrast_means))
assert math.isclose(contrast_estimate,2.5)
assert math.isclose(anova_mse,1) and math.isclose(contrast_se2,.5)
assert math.isclose(contrast_estimate**2/contrast_se2,12.5)
assert math.isclose((anova_ssb/2)/anova_mse,7)
reg_x=[0,1,2];reg_y=[1,2,2]
x_bar=sum(reg_x)/3;y_bar=sum(reg_y)/3
reg_sxx=sum((x-x_bar)**2 for x in reg_x)
reg_sxy=sum((x-x_bar)*(y-y_bar) for x,y in zip(reg_x,reg_y))
reg_syy=sum((y-y_bar)**2 for y in reg_y)
reg_ssr=reg_sxy**2/reg_sxx
reg_sse=reg_syy-reg_ssr
reg_mse=reg_sse/(3-2)
reg_t2=(reg_sxy/reg_sxx)**2*reg_sxx/reg_mse
reg_f=reg_ssr/reg_mse
assert math.isclose(reg_syy,2/3) and math.isclose(reg_ssr,.5)
assert math.isclose(reg_sse,1/6) and math.isclose(reg_ssr/reg_syy,.75)
assert math.isclose(reg_t2,reg_f) and math.isclose(reg_f,3)
assert all(x in pages['chapter-9.html'].ids for x in ('anova-contrasts','regression-ss-identity'))
assert all(x in pages['practice-9.html'].ids for x in ('P9-07','P9-08'))

# Bound a Poisson tail without using its PMF, then independently evaluate that PMF.
poisson_tail=1-math.exp(-2)*sum(2**k/math.factorial(k) for k in range(5))
assert 0<poisson_tail<2/9<2/5
assert math.isclose(poisson_tail,.052653017343711084,abs_tol=1e-12)
# Check the continuity-corrected binomial example against exact enumeration.
binom_cdf=sum(math.comb(36,k) for k in range(22))/2**36
normal_cdf=lambda z:(1+math.erf(z/math.sqrt(2)))/2
uncorrected=normal_cdf(1)
corrected=normal_cdf(7/6)
assert math.isclose(binom_cdf,.8785075229825452,abs_tol=1e-12)
assert abs(corrected-binom_cdf)<abs(uncorrected-binom_cdf)
assert math.isclose(abs(corrected-binom_cdf),.0001800275569265,abs_tol=1e-12)
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
# Enumerate the stated inverse-CDF quantiles independently of the interval formulas.
boot_values = sorted([8, 9, 9, 10, 11, 12, 12, 13])
from math import ceil
q25, q75 = (boot_values[ceil(u * len(boot_values)) - 1] for u in (.25, .75))
assert (q25, q75) == (9, 12)
assert (q25, q75) == (9, 12) and (20 - q75, 20 - q25) == (8, 11)
assert 'bootstrap-ci-inversion' in pages['chapter-10.html'].ids
assert 'P10-04' in pages['practice-10.html'].ids
# Conditional Poisson counts are binomial; thinning gives independent classes.
from math import comb
conditional = comb(4, 2) * (1/3)**2 * (2/3)**2
joint = (math.exp(-2)*2**2/math.factorial(2))*(math.exp(-4)*4)
conditional_mark = comb(3, 2)*(1/3)**2*(2/3)
assert math.isclose(conditional, 8/27)
assert math.isclose(joint, 8*math.exp(-6))
assert math.isclose(conditional_mark, 2/9)
assert all(x in pages['chapter-12.html'].ids for x in ('poisson-conditional-binomial','poisson-thinning-superposition'))
assert all(x in pages['practice-12.html'].ids for x in ('P12-05','P12-06'))
# First-step absorption equations and detailed balance, calculated independently.
q = ((0, .5), (.25, 0))
t1, t2 = 12/7, 10/7
assert math.isclose(t1, 1 + q[0][1]*t2)
assert math.isclose(t2, 1 + q[1][0]*t1)
balance_p = ((.5,.5,0),(.25,.5,.25),(0,.5,.5))
balance_pi = (.25,.5,.25)
for i in range(3):
    for j in range(3):
        assert math.isclose(balance_pi[i]*balance_p[i][j],balance_pi[j]*balance_p[j][i])
assert all(math.isclose(sum(balance_pi[i]*balance_p[i][j] for i in range(3)),balance_pi[j]) for j in range(3))
assert all(x in pages['chapter-13.html'].ids for x in ('markov-absorption-time','markov-detailed-balance'))
assert all(x in pages['practice-13.html'].ids for x in ('P13-04','P13-05'))
# Independent AR(1) covariance and discrete-spectrum checks.
phi, innovation_var = .5, 3
c0 = innovation_var / (1-phi**2)
assert math.isclose(c0, 4)
assert math.isclose(c0*phi, 2) and math.isclose(c0*phi**2, 1)
ar_spectrum = lambda w: innovation_var/(1+phi**2-2*phi*math.cos(w))
assert math.isclose(ar_spectrum(0), 12)
assert math.isclose(ar_spectrum(math.pi), 4/3)
# Midpoint integration over one period independently recovers the lag-zero covariance.
grid = 20000
average = sum(ar_spectrum(-math.pi+(j+.5)*2*math.pi/grid) for j in range(grid))/grid
assert math.isclose(average, 4, abs_tol=1e-8)
assert all(x in pages['chapter-14.html'].ids for x in ('stationary-ar1','ar1-discrete-spectrum'))
assert all(x in pages['practice-14.html'].ids for x in ('P14-05','P14-06'))
# Order-statistic CDF from an independent binomial count and density integral.
median_cdf = sum(math.comb(3,j)*(.25**j)*(.75**(3-j)) for j in (2,3))
assert math.isclose(median_cdf, 5/32)
def simpson_check(fn, lo, hi, steps=20000):
    step=(hi-lo)/steps
    return step/3*(fn(lo)+fn(hi)+4*sum(fn(lo+i*step) for i in range(1,steps,2))+2*sum(fn(lo+i*step) for i in range(2,steps,2)))
assert math.isclose(simpson_check(lambda x:6*x*(1-x),0,1),1,abs_tol=1e-10)
assert math.isclose(simpson_check(lambda x:x*math.exp(-x/2)/4,2,80),2/math.e,abs_tol=1e-9)
assert math.isclose(simpson_check(lambda x:x*x*math.exp(-x/2)/4,0,80),4,abs_tol=1e-9)
assert all(x in pages['chapter-6.html'].ids for x in ('sample-order-statistics','chi-square-density'))
assert all(x in pages['practice-6.html'].ids for x in ('P6-05','P6-06'))
# Chapter 3 sample-audit additions: independent enumeration, quadrature and
# coordinate-area calculations for original examples, not textbook answers.
bits=list(__import__('itertools').product((0,1),repeat=4))
assert sum(a+b==1 and max(c,d)==1 for a,b,c,d in bits)/16==3/8
assert sum(a+b==0 and b+c==0 for a,b,c,d in bits)/16==1/8
mapped={}
for x,y,p in [(0,0,1/8),(0,1,3/8),(1,0,1/4),(1,1,1/4)]:
    key=(x+y,x*y);mapped[key]=mapped.get(key,0)+p
assert mapped=={(0,0):1/8,(1,0):5/8,(2,1):1/4}
# Original (x,y) triangle 0<y<x and x+y<1/2, split at x=1/4.
triangle_area=simpson_check(lambda x:x,0,.25)+simpson_check(lambda x:.5-x,.25,.5)
assert math.isclose(triangle_area,1/16,abs_tol=1e-10)
for y in (.04,.25,.81):
    posterior_mass=simpson_check(lambda x:1/(-x*math.log(y)),y,1)
    posterior_tail=simpson_check(lambda x:1/(-x*math.log(y)),math.sqrt(y),1)
    assert math.isclose(posterior_mass,1,abs_tol=1e-9)
    assert math.isclose(posterior_tail,.5,abs_tol=1e-9)
gamma_tail=simpson_check(lambda s:27*s*s*math.exp(-3*s)/2,1,20)
assert math.isclose(gamma_tail,17/(2*math.e**3),abs_tol=1e-9)
assert math.isclose(simpson_check(lambda s:27*s*s*math.exp(-3*s)/2,0,20),1,abs_tol=1e-9)
assert math.isclose(simpson_check(lambda s:s*27*s*s*math.exp(-3*s)/2,0,20),1,abs_tol=1e-9)
# Numeric convolution agrees with the completed-square normal result.
def normal_pdf(x,mu,var):return math.exp(-(x-mu)**2/(2*var))/math.sqrt(2*math.pi*var)
for z in (0,8,14):
    convolved=simpson_check(lambda u:normal_pdf(u,3,36)*normal_pdf(z-1-u,4,36),-70,80)
    assert math.isclose(convolved,normal_pdf(z,8,72),rel_tol=1e-9)
t0=math.log(2)
assert math.isclose(math.exp(-5*t0),1/32)
assert math.isclose(1-(1-math.exp(-2*t0))*(1-math.exp(-3*t0)),11/32)
assert math.isclose(simpson_check(lambda s:6*(math.exp(-2*s)-math.exp(-3*s)),t0,30),.5,abs_tol=1e-9)
assert math.isclose(simpson_check(lambda r:r*r*(r/4)*math.exp(-r*r/8),0,30),8,abs_tol=1e-9)
assert math.isclose(simpson_check(lambda t:1/(math.pi*(1+t*t)),-math.sqrt(3),math.sqrt(3)),2/3,abs_tol=1e-10)
# Verify t²/F quantile relation with two different numerical integrals.
def t5_pdf(t):return math.gamma(3)/(math.sqrt(5*math.pi)*math.gamma(2.5))*(1+t*t/5)**-3
central_t=simpson_check(t5_pdf,-2.57058,2.57058)
# Substitute q=s² to remove the q^-1/2 singularity in F(1,5).
f_const=math.sqrt(1/5)*math.gamma(3)/(math.gamma(.5)*math.gamma(2.5))
central_f=simpson_check(lambda s:2*f_const*(1+s*s/5)**-3,0,2.57058)
assert math.isclose(central_t,.95,abs_tol=2e-7)
assert math.isclose(central_t,central_f,abs_tol=1e-10)
assert math.isclose(2.57058**2,6.60788,abs_tol=5e-6)
assert all(f'P3-{i:02}' in pages['practice-3.html'].ids for i in range(11,20))
assert all(f'P6-{i:02}' in pages['practice-6.html'].ids for i in (7,8))
assert all(f'audit-3.{i}' in pages['sources.html'].ids for i in range(1,6))
# Original chapter-3 exam: enumerate discrete cells and independently check
# nontrivial integration regions, the Gamma tail and system reliability.
exam_joint=[[.1,.2,.3],[.1,.1,.2]]
assert math.isclose(sum(map(sum,exam_joint)),1)
assert math.isclose(sum(exam_joint[0][:2]),.3)
assert math.isclose(exam_joint[1][2]/sum(exam_joint[1]),.5)
assert not math.isclose(exam_joint[0][0],sum(row[0] for row in exam_joint)*sum(exam_joint[0]))
assert math.isclose(simpson_check(lambda y:3*y*y/8,0,2),1,abs_tol=1e-10)
assert math.isclose(simpson_check(lambda x:3*(4-x*x)/16,0,2),1,abs_tol=1e-10)
assert math.isclose(simpson_check(lambda y:3*y*y/16,0,2),.5,abs_tol=1e-10)
# V>3 means y>3x in 0<x<y<1, a triangle with area 1/6 and density 2.
assert math.isclose(simpson_check(lambda x:2*(1-3*x),0,1/3),1/3,abs_tol=1e-10)
assert math.isclose(simpson_check(lambda s:4*s*s*math.exp(-2*s),2,40),13*math.exp(-4),abs_tol=1e-9)
assert math.exp(-2)<2/math.e-math.exp(-2)<2/math.e
assert all(q['id'] in pages[f'exam-{e["id"]}.html'].ids for e in exams for q in e['questions'])
# Exams 4–6: use direct expectation sums, covariance matrix multiplication,
# numerical quadrature and count enumeration to check the authored results.
law=[(-1,.25),(0,.5),(2,.25)]
ex=sum(x*p for x,p in law)
vx=sum((x-ex)**2*p for x,p in law)
assert math.isclose(ex,.25) and math.isclose(vx,19/16)
assert math.isclose(sum((2*x+1)*p for x,p in law),1.5)
assert math.isclose(simpson_check(lambda x:x**4/2,-1,1),.2,abs_tol=1e-10)
assert math.isclose(simpson_check(lambda x:(x*x-1/3)**2/2,-1,1),4/45,abs_tol=1e-10)
sigma=[[4,1],[1,9]];transform=[[1,1],[2,-1]]
transformed=[[sum(transform[i][k]*sigma[k][l]*transform[j][l]
                   for k in range(2) for l in range(2)) for j in range(2)] for i in range(2)]
assert transformed==[[15,0],[0,21]]
assert math.isclose(100/10000,.01)
normal_mass=math.erf(10.5/math.sqrt(75))
exact_mass=sum(math.comb(200,k)*.25**k*.75**(200-k) for k in range(40,61))
assert math.isclose(normal_mass,.9135892670263,abs_tol=1e-12)
assert math.isclose(exact_mass,.914107230445094,abs_tol=1e-12)
assert math.isclose(exact_mass-normal_mass,.000517963418794,abs_tol=1e-12)
# At x=1/4, a U(0,1) observation falls in one of four equal bins; count
# all 4^5 equally likely bin sequences instead of evaluating the CDF polynomial.
from itertools import product
median_successes=sum(sum(v==0 for v in xs)>=3 for xs in product(range(4),repeat=5))
assert median_successes/4**5==53/512
assert math.isclose(simpson_check(lambda x:30*x*x*(1-x)**2,0,.25),53/512,abs_tol=1e-10)
assert math.isclose(simpson_check(lambda v:v*math.exp(-v/2)/4,6,90),4*math.exp(-3),abs_tol=1e-9)
assert math.isclose(sum((x-3)**2 for x in [1,2,4,5])/3,10/3)
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
# Gauss–Markov example: enumerate all Rademacher errors, without assuming
# normality, then compare the variance of the two unbiased slope estimators.
errors=list(product([-1,1],repeat=3))
slope_ols=[(e[2]-e[0])/2 for e in errors]
slope_other=[e[1]-e[0] for e in errors]
assert mean(slope_ols)==mean(slope_other)==0
assert mean(x*x for x in slope_ols)==.5
assert mean(x*x for x in slope_other)==2
# Independently form the orthogonal projection and check both the actual
# residuals and the rank/trace responsible for the chi-square degrees of freedom.
design=[-1,0,1,2]; response=[0,1,1,4]
hat=[[.25+(x-.5)*(y-.5)/5 for y in design] for x in design]
for i,j in product(range(4),repeat=2):
    assert math.isclose(sum(hat[i][k]*hat[k][j] for k in range(4)),hat[i][j],abs_tol=1e-12)
assert math.isclose(sum(hat[i][i] for i in range(4)),2)
projection=[sum(h*y for h,y in zip(row,response)) for row in hat]
residual=[y-fit for y,fit in zip(response,projection)]
assert all(math.isclose(r,t,abs_tol=1e-12) for r,t in zip(residual,[.3,.1,-1.1,.7]))
assert math.isclose(sum(r*r for r in residual),1.8)
assert math.isclose(-hat[0][1],-.4)
assert math.isclose((1.2/math.sqrt(.9/5))**2,8)
# Exact bootstrap maximum distribution by 27 ordered index samples.
boot_maxima=[max(xs) for xs in product(range(3),repeat=3)]
assert [boot_maxima.count(j) for j in range(3)]==[1,7,19]
assert math.isclose(1-(1-1/10000)**10000,1-math.exp(-1),abs_tol=2e-5)
# Direct time integration for independent, fixed coefficient choices confirms
# that longer whole-period windows retain the same random power factor.
for aa,bb in [(1,2),(-.5,1),(2,0)]:
    for periods in [1,3]:
        window=2*math.pi*periods
        trajectory=lambda t:aa*math.cos(t)+bb*math.sin(t)
        assert math.isclose(simpson_check(trajectory,0,window)/window,0,abs_tol=1e-10)
        for lag in [0,.7]:
            actual=simpson_check(lambda t:trajectory(t)*trajectory(t+lag),0,window)/window
            assert math.isclose(actual,(aa*aa+bb*bb)*math.cos(lag)/2,abs_tol=1e-10)
assert math.isclose(1-math.exp(-.5)+math.exp(-1.5),.616599500435796,abs_tol=1e-12)
# Common moments: direct probability sums rather than factorial identities.
bin_law=[math.comb(5,k)*.4**k*.6**(5-k) for k in range(6)]
assert math.isclose(sum(k**2*p for k,p in enumerate(bin_law)),5.2)
assert math.isclose(sum(k**3*p for k,p in enumerate(bin_law)),15.44)
assert math.isclose(sum(k**3*math.exp(-3)*3**k/math.factorial(k) for k in range(80)),57)
geom_m1=sum(k*.25*.75**(k-1) for k in range(1,501))
geom_m2=sum(k*k*.25*.75**(k-1) for k in range(1,501))
assert math.isclose(geom_m1,4) and math.isclose(geom_m2-geom_m1**2,12)
from itertools import combinations
hyper_counts=[sum(i<4 for i in group) for group in combinations(range(10),5)]
assert len(hyper_counts)==252 and mean(hyper_counts)==2
assert math.isclose(mean((x-2)**2 for x in hyper_counts),2/3)
assert [hyper_counts.count(k) for k in range(5)]==[6,60,120,60,6]
loss_law=[(0,.4),(2,.2),(5,.4)]
abs_loss=lambda m:sum(abs(x-m)*p for x,p in loss_law)
sq_loss=lambda m:sum((x-m)**2*p for x,p in loss_law)
assert math.isclose(abs_loss(2),2) and math.isclose(abs_loss(2.4),2.08)
assert math.isclose(sq_loss(2),5.2) and math.isclose(sq_loss(2.4),5.04)
step=1e-5
assert math.isclose((abs_loss(2+step)-abs_loss(2))/step,.2,abs_tol=1e-8)
assert math.isclose((abs_loss(2)-abs_loss(2-step))/step,-.2,abs_tol=1e-8)
assert all(math.isclose((abs(m)+abs(4-m))/2,2) for m in [0,.5,1,2,3,4])
assert math.isclose(simpson_check(lambda z:z*z*math.exp(-z*z/2)/math.sqrt(2*math.pi),-10,10),1,abs_tol=1e-10)
assert math.isclose(simpson_check(lambda z:z**4*math.exp(-z*z/2)/math.sqrt(2*math.pi),-10,10),3,abs_tol=1e-10)
# Estimation/testing papers: direct integrals, exact probabilities and fitted
# expected counts independently check the reported answers and tail directions.
assert math.isclose(simpson_check(lambda m:m*4*m**3/5**4,0,5),4,abs_tol=1e-10)
exposure=sum([.5,1,2])+2*3
assert exposure==9.5 and math.isclose(3/exposure,6/19)
assert 9/25<1/2
prior_likelihood=lambda mu:math.exp(-(mu-1)**2/4-4*(3-mu)**2/8)
normalizer=simpson_check(prior_likelihood,-20,20)
post_mean=simpson_check(lambda mu:mu*prior_likelihood(mu),-20,20)/normalizer
post_var=simpson_check(lambda mu:(mu-post_mean)**2*prior_likelihood(mu),-20,20)/normalizer
assert math.isclose(post_mean,7/3,abs_tol=1e-10)
assert math.isclose(post_var,2/3,abs_tol=1e-10)
assert math.isclose(sum(math.comb(10,k)*.5**10 for k in range(8,11)),7/128)
power=sum(math.comb(10,k)*.8**k*.2**(10-k) for k in range(8,11))
assert math.isclose(power,.6777995264,abs_tol=1e-12)
assert 4*(1.645+1.282)**2>34 and 4*(1.645+1.282)**2<35
gof_observed=[20,30,50];gof_expected=[25,25,50]
assert math.isclose(sum((o-e)**2/e for o,e in zip(gof_observed,gof_expected)),2)
table=[[30,10],[20,40]]
rows=list(map(sum,table));cols=[sum(row[j] for row in table) for j in range(2)]
expected=[[r*c/100 for c in cols] for r in rows]
assert expected==[[20,20],[30,30]]
pearson=sum((table[i][j]-expected[i][j])**2/expected[i][j] for i,j in product(range(2),repeat=2))
assert math.isclose(pearson,50/3)
assert math.isclose(math.erfc(math.sqrt(pearson/2)),.0000445570906040562,abs_tol=1e-14)
# Application papers: compute directly from the authored datasets.
exam_groups=[[1,2,3],[2,3,4],[5,6,7]]
grand=mean(sum(exam_groups,[]))
ss_within=sum((x-mean(g))**2 for g in exam_groups for x in g)
ss_between=sum(len(g)*(mean(g)-grand)**2 for g in exam_groups)
assert math.isclose(ss_within,6) and math.isclose(ss_between,26)
cells=[[[0,2],[2,4]],[[2,4],[0,2]]]
cell_means=[[mean(g) for g in row] for row in cells]
assert sum((x-cell_means[i][j])**2 for i,j in product(range(2),repeat=2) for x in cells[i][j])==8
assert sum(2*(cell_means[i][j]-2)**2 for i,j in product(range(2),repeat=2))==8
xx=[0,1,2,3];yy=[0,2,2,3]
sx=sum((x-mean(xx))**2 for x in xx)
sxy=sum((x-mean(xx))*(y-mean(yy)) for x,y in zip(xx,yy))
slope=sxy/sx;intercept=mean(yy)-slope*mean(xx)
ss_error=sum((y-intercept-slope*x)**2 for x,y in zip(xx,yy))
ss_total=sum((y-mean(yy))**2 for y in yy)
assert math.isclose(slope,.9) and math.isclose(intercept,.4)
assert math.isclose(ss_error,.7)
assert math.isclose(1-ss_error/ss_total,81/95)
assert math.isclose((ss_total-ss_error)/(ss_error/2),81/7)
index_sums=[sum(xs) for xs in product(range(3),repeat=3)]
assert [index_sums.count(i) for i in range(7)]==[1,3,6,7,6,3,1]
assert math.isclose(mean(((2*k/3)-2)**2 for k in index_sums),8/9)
poisson_sample=[9+sign*d for d in [6,5,3,2,2,2,2,2] for sign in [-1,1]]
assert mean(poisson_sample)==9 and variance(poisson_sample)==12
assert math.isclose(sum((x-9)**2 for x in poisson_sample)/16**2,45/64)
resampled=list(product([-2.5,-.5,.5,2.5],repeat=4))
assert sum(len(set(xs))==1 for xs in resampled)/len(resampled)==1/64
assert sum(abs(mean(xs))>=1.5 for xs in resampled)==30
# Process/Markov proofs and final papers: direct integrations and path/matrix
# calculations independently check the stated moments, tails and conventions.
normal0=lambda z:math.exp(-z*z/2)/math.sqrt(2*math.pi)
mix_sum_m2=simpson_check(lambda z:.5*(2*z)**2*normal0(z),-10,10)
mix_sum_m4=simpson_check(lambda z:.5*(2*z)**4*normal0(z),-10,10)
assert math.isclose(mix_sum_m2,2) and math.isclose(mix_sum_m4,24)
assert not math.isclose(mix_sum_m4,3*mix_sum_m2**2)  # Non-Gaussian sum.
def window_cov(s,t,h):
    return min(s+h,t+h)-min(s+h,t)-min(s,t+h)+min(s,t)
for h in [1,2]:
    for s,t in product([0,.5,1,2,3],repeat=2):
        assert math.isclose(window_cov(s,t,h),max(h-abs(s-t),0),abs_tol=1e-12)
def row_times(u,p):
    return [sum(u[i]*p[i][j] for i in range(len(u))) for j in range(len(p))]
transition=[[.7,.3],[.2,.8]]
tv=lambda u,v:sum(abs(a-b) for a,b in zip(u,v))/2
stationary=[.4,.6];u=[1.,0.]
for n in range(30):
    assert math.isclose(tv(u,stationary),.6*.5**n,abs_tol=1e-12)
    assert tv(u,stationary)<=.6*.6**n+1e-12
    u=row_times(u,transition)
assert min(n for n in range(30) if .6*.6**n<=.01)==9
assert min(n for n in range(30) if .6*.5**n<=.01)==6
first_return=[.7]+[.06*.8**(n-2) for n in range(2,301)]
assert math.isclose(sum(first_return),1,abs_tol=1e-12)
assert math.isclose(sum((i+1)*p for i,p in enumerate(first_return)),2.5,abs_tol=1e-12)
# Absorption expectations via summing transient survival probabilities, rather
# than reusing the displayed first-step linear equations.
transient=[[.5,.5],[.25,.5]]
for initial,target in [([1.,0.],8),([0.,1.],6)]:
    surviving=initial;expected_time=0
    for _ in range(1000):
        expected_time+=sum(surviving)
        surviving=row_times(surviving,transient)
    assert math.isclose(expected_time,target,abs_tol=1e-10)
reversible=[[.5,.5,0],[.25,.5,.25],[0,.5,.5]];pi=[.25,.5,.25]
assert row_times(pi,reversible)==pi
assert all(pi[i]*reversible[i][j]==pi[j]*reversible[j][i] for i,j in product(range(3),repeat=2))
for initial,target in [([1.,0.],6),([0.,1.],8)]:
    surviving=initial;expected_time=0
    for _ in range(1000):
        expected_time+=sum(surviving)
        surviving=row_times(surviving,[[.5,.25],[.5,.5]])
    assert math.isclose(expected_time,target,abs_tol=1e-10)
assert math.isclose(.5+.5*(1+6),1/pi[0])
assert math.isclose(math.exp(-4)*4**3/math.factorial(3),.1953668148131646,abs_tol=1e-12)
assert math.isclose(simpson_check(lambda t:9*t*math.exp(-3*t),0,20),1,abs_tol=1e-10)
assert math.isclose(simpson_check(lambda t:t*9*t*math.exp(-3*t),0,20),2/3,abs_tol=1e-10)
assert math.isclose(simpson_check(lambda t:(t-2/3)**2*9*t*math.exp(-3*t),0,20),2/9,abs_tol=1e-10)
assert math.isclose(math.comb(4,2)*.25**2*.75**2,27/128)
# R-paper data: existing execution report remains hashed to the exact code.
paired_d=[a-b for a,b in zip([7,8,10,11,14],[6,9,9,10,12])]
assert mean(paired_d)==.8 and variance(paired_d)==1.2
assert math.isclose(mean(paired_d)/math.sqrt(variance(paired_d)/5),1.6329931618554523)
rx=[0,1,2];ry=[1,2,2]
rb=sum((x-mean(rx))*(y-mean(ry)) for x,y in zip(rx,ry))/sum((x-mean(rx))**2 for x in rx)
ra=mean(ry)-rb*mean(rx)
rsse=sum((y-ra-rb*x)**2 for x,y in zip(rx,ry))
assert math.isclose(ra,7/6) and rb==.5 and math.isclose(rsse,1/6)
assert math.isclose(12.7062*math.sqrt(rsse/3),2.994874060076316,abs_tol=1e-5)
# Frequency conventions: numerical Fourier integrals and spectral total mass.
for omega in [0,.5,1,2,5]:
    fourier=2*simpson_check(lambda t:4*math.exp(-2*t)*math.cos(omega*t),0,25)
    assert math.isclose(fourier,16/(4+omega**2),abs_tol=1e-9)
assert math.isclose(simpson_check(lambda w:3/(1.25-math.cos(w)),-math.pi,math.pi)/(2*math.pi),4,abs_tol=1e-10)
for T in [.5,1,5,10]:
    direct=2*simpson_check(lambda t:(T-t)*4*math.exp(-2*t),0,T)/T**2
    assert math.isclose(direct,4/T-2*(1-math.exp(-2*T))/T**2,abs_tol=1e-9)
bad=[[1,.9,0],[.9,1,.9],[0,.9,1]];coeff=[1,-2,1]
assert math.isclose(sum(coeff[i]*bad[i][j]*coeff[j] for i,j in product(range(3),repeat=2)),-1.2)
# Initial-model additions: integrate the parameter region, enumerate finite
# supports and verify inverse-CDF events on a deterministic uniform grid.
needle_area=simpson_check(lambda angle:1.5*math.sin(angle),0,math.pi)
assert math.isclose(needle_area/(2*math.pi),3/(2*math.pi),abs_tol=1e-12)
assert math.isclose(3*math.sin(math.pi/6)/4,3/8)
discrete_support=[1,2,4,8]
assert mean(discrete_support)==15/4
assert mean((x-15/4)**2 for x in discrete_support)==115/16
for n,p,expected_modes in [(9,.3,[2,3]),(8,.3,[2]),(5,.5,[2,3])]:
    law=[math.comb(n,k)*p**k*(1-p)**(n-k) for k in range(n+1)]
    maximum=max(law)
    assert [k for k,v in enumerate(law) if math.isclose(v,maximum,rel_tol=1e-12)]==expected_modes
mixture_cdf=lambda x:0 if x<0 else (.25 if x<=1 else (.25+.375*(x-1) if x<3 else 1))
mixture_quantile=lambda u:0 if u<=.25 else 1+8/3*(u-.25)
assert mixture_quantile(.25)==0 and math.isclose(mixture_quantile(.5),5/3)
assert math.isclose(mixture_quantile(.9),41/15)
uniform_grid=[(i+.5)/10000 for i in range(10000)]
quantiles=[mixture_quantile(u) for u in uniform_grid]
for x in [-1,0,.5,1,1.5,2,3,4]:
    assert all((q<=x)==(u<=mixture_cdf(x)) for u,q in zip(uniform_grid,quantiles))
    assert math.isclose(sum(q<=x for q in quantiles)/len(quantiles),mixture_cdf(x),abs_tol=1e-4)
assert sum(mixture_cdf(q)==.25 for q in quantiles)/len(quantiles)==.25
# Non-identical Bernoulli example: exact Poisson-binomial convolution, not a
# binomial approximation with the mean success probability.
success_rates=[.2 if i%2==0 else .5 for i in range(200)]
poisson_binomial=[1.]
for rate in success_rates:
    out=[0.]*(len(poisson_binomial)+1)
    for k,prob in enumerate(poisson_binomial):
        out[k]+=prob*(1-rate);out[k+1]+=prob*rate
    poisson_binomial=out
mu_sum=sum(k*p for k,p in enumerate(poisson_binomial))
var_sum=sum((k-mu_sum)**2*p for k,p in enumerate(poisson_binomial))
assert math.isclose(mu_sum,70,abs_tol=1e-10) and math.isclose(var_sum,41,abs_tol=1e-10)
approx_non_iid=(1+math.erf((80.5-70)/math.sqrt(82)))/2
assert math.isclose(approx_non_iid,.9495,abs_tol=5e-5)
assert abs(sum(poisson_binomial[:81])-approx_non_iid)<.002
third_sum=sum(p*(1-p)**3+(1-p)*p**3 for p in success_rates)
assert third_sum/41**1.5<=1/math.sqrt(41)
# Enumerate the counterexample exactly for small n; its support bound and
# characteristic-function limit demonstrate a uniform rather than normal law.
for n in range(1,9):
    sign_sums=[sum(2**i*sign for i,sign in enumerate(signs)) for signs in product([-1,1],repeat=n)]
    assert sorted(sign_sums)==list(range(-(2**n-1),2**n,2))
    b2=(4**n-1)/3
    assert mean(sign_sums)==0 and math.isclose(mean(x*x for x in sign_sums),b2)
    assert max(abs(x) for x in sign_sums)/math.sqrt(b2)<math.sqrt(3)
for t in [.5,1,2]:
    n=20;b=math.sqrt((4**n-1)/3)
    actual=math.prod(math.cos(t*2**i/b) for i in range(n))
    target=math.sin(math.sqrt(3)*t)/(math.sqrt(3)*t)
    assert math.isclose(actual,target,abs_tol=1e-10)
wald_margin=1.96*math.sqrt(.3*.7/100)
assert math.isclose(.3-wald_margin,.2101815163771056,abs_tol=1e-12)
assert math.isclose(.3+wald_margin,.3898184836228944,abs_tol=1e-12)
# Confidence calibration: compute full finite binomial laws and invert tails
# numerically, independently of the closed-form interval examples.
def binomial_law(n,p):
    return [math.comb(n,k)*p**k*(1-p)**(n-k) for k in range(n+1)]
def binomial_tail_root(n,k,target,right):
    lo,hi=0.,1.
    for _ in range(65):
        mid=(lo+hi)/2
        law=binomial_law(n,mid)
        tail=sum(law[k:] if right else law[:k+1])
        if (tail<target)==right: lo=mid
        else: hi=mid
    return (lo+hi)/2
cp_bounds=[(0. if k==0 else binomial_tail_root(10,k,.025,True),
            1. if k==10 else binomial_tail_root(10,k,.025,False)) for k in range(11)]
assert math.isclose(cp_bounds[0][1],.30849710781876083,abs_tol=1e-12)
assert math.isclose(cp_bounds[10][0],.6915028921812392,abs_tol=1e-12)
assert math.isclose(binomial_tail_root(10,0,.05,False),.2588655508930523,abs_tol=1e-12)
for p in [i/400 for i in range(401)]:
    law=binomial_law(10,p)
    coverage=sum(prob for prob,(lo,hi) in zip(law,cp_bounds) if lo-1e-14<=p<=hi+1e-14)
    assert coverage>=.95-1e-12
assert .75**10>.05  # Wald zero-success point interval alone loses >5% here.
z=1.96
assert math.isclose(z*z/(10+z*z),.2775401687666166,abs_tol=1e-12)
for n in [1,2,10,30]:
    for k in range(n+1):
        phat=k/n;a=1+z*z/n
        center=(phat+z*z/(2*n))/a
        half=z*math.sqrt(phat*(1-phat)/n+z*z/(4*n*n))/a
        lo,hi=center-half,center+half
        assert -1e-14<=lo<=hi<=1+1e-14
        for p in [.01,.1,.25,.5,.75,.9,.99]:
            assert (lo<=p<=hi)==(n*(phat-p)**2<=z*z*p*(1-p))
# Valid p-values for H0:p<=.5: enumerate every rejection set for attainable
# thresholds at a grid of null parameters, including their boundary.
null_law=binomial_law(10,.5)
tail_values=[sum(null_law[k:]) for k in range(11)]
assert math.isclose(tail_values[8],7/128) and math.isclose(tail_values[9],11/1024)
for p in [i/100 for i in range(51)]:
    law=binomial_law(10,p)
    for alpha in tail_values+[0,.01,.05,.1,.5,1]:
        assert sum(prob for prob,pval in zip(law,tail_values) if pval<=alpha)<=alpha+1e-12
# One fitted direction: check the limiting residual projection algebra and
# compute the example directly from observed and fitted class counts.
probs=[.2,.2,.3,.3];q=[math.sqrt(p) for p in probs]
j=[.5,.5,-.5,-.5];avec=[x/math.sqrt(p) for x,p in zip(j,probs)]
information=sum(x*x for x in avec)
assert abs(sum(x*y for x,y in zip(q,avec)))<1e-12
projection=[[(1. if i==j else 0.)-q[i]*q[j]-avec[i]*avec[j]/information for j in range(4)] for i in range(4)]
assert math.isclose(sum(projection[i][i] for i in range(4)),2)
for i,j in product(range(4),repeat=2):
    assert math.isclose(projection[i][j],projection[j][i],abs_tol=1e-12)
    assert math.isclose(sum(projection[i][k]*projection[k][j] for k in range(4)),projection[i][j],abs_tol=1e-12)
assert math.isclose(sum((o-100*p)**2/(100*p) for o,p in zip([18,22,33,27],probs)),1)
assert math.isclose(math.exp(-.5),.6065306597126334,abs_tol=1e-12)
# Exact zero-correlation laws: integrate after r=sin(theta), avoiding endpoint
# singularities and checking both normalization and the null second moment.
for n in [3,4,5,6,8,12]:
    nu=n-2
    constant=math.gamma((nu+1)/2)/(math.sqrt(math.pi)*math.gamma(nu/2))
    theta_density=lambda t:constant*math.cos(t)**(n-3)
    assert math.isclose(simpson_check(theta_density,-math.pi/2,math.pi/2),1,abs_tol=1e-10)
    assert math.isclose(simpson_check(lambda t:math.sin(t)**2*theta_density(t),-math.pi/2,math.pi/2),1/(n-1),abs_tol=1e-10)
    for r in [-.8,-.2,0,.3,.9]:
        t=math.sqrt(nu)*r/math.sqrt(1-r*r)
        t_pdf=math.gamma((nu+1)/2)/(math.sqrt(nu*math.pi)*math.gamma(nu/2))*(1+t*t/nu)**(-(nu+1)/2)
        assert math.isclose(t_pdf*math.sqrt(nu)*(1-r*r)**(-1.5),constant*(1-r*r)**((nu-2)/2),rel_tol=1e-12)
assert math.isclose(2*simpson_check(lambda r:.75*(1-r*r),.8,1),.056,abs_tol=1e-12)
assert math.isclose(.8*math.sqrt(4)/math.sqrt(1-.8**2),8/3)
# Constrained least squares: rational arithmetic on actual data with a
# non-diagonal Gram matrix; verify constraints and both residual sums directly.
from fractions import Fraction
def transpose_check(a):
    return [list(row) for row in zip(*a)]
def matmul_check(a,b):
    return [[sum(x*y for x,y in zip(row,col)) for col in zip(*b)] for row in a]
def inverse_check(a):
    n=len(a)
    rows=[[Fraction(x) for x in row]+[Fraction(i==j) for j in range(n)] for i,row in enumerate(a)]
    for j in range(n):
        pivot=next(i for i in range(j,n) if rows[i][j])
        rows[j],rows[pivot]=rows[pivot],rows[j]
        scale=rows[j][j];rows[j]=[x/scale for x in rows[j]]
        for i in range(n):
            if i!=j:
                scale=rows[i][j];rows[i]=[x-scale*y for x,y in zip(rows[i],rows[j])]
    return [row[n:] for row in rows]
design=[[1,x,x*x] for x in [-3,-2,-1,0,0,1,2,3]]
response=[[v] for v in [1,2,2,1,3,4,3,6]]
xt=transpose_check(design);gram=matmul_check(xt,design);g=inverse_check(gram)
beta=matmul_check(g,matmul_check(xt,response))
constraint=[[0,1,-1],[1,0,1]];target=[[Fraction(1,2)],[Fraction(1)]]
delta=[[a[0]-b[0]] for a,b in zip(matmul_check(constraint,beta),target)]
v=matmul_check(matmul_check(constraint,g),transpose_check(constraint))
adjust=matmul_check(matmul_check(matmul_check(g,transpose_check(constraint)),inverse_check(v)),delta)
restricted=[[a[0]-b[0]] for a,b in zip(beta,adjust)]
assert matmul_check(constraint,restricted)==target
full_fit=matmul_check(design,beta);restricted_fit=matmul_check(design,restricted)
full_sse=sum((y[0]-f[0])**2 for y,f in zip(response,full_fit))
restricted_sse=sum((y[0]-f[0])**2 for y,f in zip(response,restricted_fit))
w=matmul_check(matmul_check(transpose_check(delta),inverse_check(v)),delta)[0][0]
assert restricted_sse-full_sse==w and w>=0
assert Fraction(1)**2/Fraction(1,10)+Fraction(-1)**2/Fraction(1,6)==16
assert (16/2)/(18/9)==4
# Risk is evaluated from coordinate-wise mean errors and noise variances, with
# a second calculation by exact finite noise enumeration for a nonnormal model.
d=10.;sigma2=1.;beta_true=4.
risk=lambda lam:(sigma2*d+lam*lam*beta_true**2)/(d+lam)**2
assert math.isclose(risk(1),26/121)
assert math.isclose(risk(.01),.09981626764843547,abs_tol=1e-12)
assert risk(.01)<risk(0)<risk(1)
for lam in [0,.01,.1,1,5]:
    ols_values=[beta_true+sign*math.sqrt(sigma2/d) for sign in [-1,1]]
    finite_risk=mean((d*b/(d+lam)-beta_true)**2 for b in ols_values)
    assert math.isclose(finite_risk,risk(lam),abs_tol=1e-12)
step=1e-6
assert math.isclose((risk(step)-risk(0))/step,-.02,abs_tol=1e-6)
# Given N(T)=n: integrate beta order-statistic marginals and enumerate four
# independent uniform subinterval labels to check conditional count dependence.
for n in range(1,9):
    for k in range(1,n+1):
        constant=math.factorial(n)/(math.factorial(k-1)*math.factorial(n-k))
        density_order=lambda u:constant*u**(k-1)*(1-u)**(n-k)
        assert math.isclose(simpson_check(density_order,0,1),1,abs_tol=1e-9)
        assert math.isclose(simpson_check(lambda u:u*density_order(u),0,1),k/(n+1),abs_tol=1e-9)
labels=list(product(range(4),repeat=4))
count_first=[sum(x==0 for x in row) for row in labels]
count_last=[sum(x>=2 for x in row) for row in labels]
assert sum(c==0 for c in count_first)==81
assert sum(sum(x<2 for x in row)>=3 for row in labels)/256==5/16
cov_conditional=mean(a*b for a,b in zip(count_first,count_last))-mean(count_first)*mean(count_last)
assert cov_conditional==-.5
# For a concrete random harmonic process, evaluate the actual squared
# difference averaged over independent signs A/B, rather than only the formula.
for t,h in product([0,.2,1,3],[-.5,.001,1,2*math.pi]):
    increments=[a*(math.cos(t+h)-math.cos(t))+b*(math.sin(t+h)-math.sin(t)) for a,b in product([-1,1],repeat=2)]
    assert math.isclose(mean(x*x for x in increments),2*(1-math.cos(h)),abs_tol=1e-12)
for h in [1e-2,1e-3,1e-4]:
    diff=-8*math.expm1(-2*h)
    assert math.isclose((diff/h**2)*h,16,rel_tol=.011)
    assert diff<16*h
for h,tau in product([.001,.1,.7],[0,.2,1,2,7]):
    r=lambda t:4*math.exp(-2*abs(t))
    assert (r(tau+h)-r(tau))**2<=r(0)*2*(r(0)-r(h))+1e-12
# Type-II exponential inference: integrate the gamma density and reciprocal
# moments, and invert its CDF independently of the rounded supplied quantiles.
failure_times=[2,4,7];n_life=5;r_life=3
previous=0;weighted_spacings=[]
for j,t in enumerate(failure_times):
    weighted_spacings.append((n_life-j)*(t-previous));previous=t
assert weighted_spacings==[10,8,9]
assert sum(weighted_spacings)==sum(failure_times)+(n_life-r_life)*failure_times[-1]==27
gamma_density=lambda w:w*w*math.exp(-w)/2
assert math.isclose(simpson_check(gamma_density,0,50),1,abs_tol=1e-9)
assert math.isclose(simpson_check(lambda w:w*gamma_density(w),0,50),3,abs_tol=1e-9)
assert math.isclose(simpson_check(lambda w:(w-3)**2*gamma_density(w),0,50),3,abs_tol=1e-9)
assert math.isclose(simpson_check(lambda w:w*math.exp(-w)/2,0,50),.5,abs_tol=1e-8)
chi6_cdf=lambda x:1-math.exp(-x/2)*(1+x/2+x*x/8)
def chi6_quantile_check(prob):
    lo,hi=0.,60.
    for _ in range(70):
        mid=(lo+hi)/2
        if chi6_cdf(mid)<prob:lo=mid
        else:hi=mid
    return (lo+hi)/2
lower=chi6_quantile_check(.025);upper=chi6_quantile_check(.975)
assert math.isclose(lower,1.237344,abs_tol=5e-7)
assert math.isclose(upper,14.449375,abs_tol=5e-7)
assert math.isclose(lower/54,.0229138,abs_tol=5e-8)
assert math.isclose(upper/54,.267581,abs_tol=5e-7)
assert math.isclose(chi6_cdf(upper)-chi6_cdf(lower),.95,abs_tol=1e-12)
# General sample moments: enumerate finite iid populations independently of the
# fourth-moment derivation, including uncorrelated yet dependent mean/variance.
for population,weights,n in [([0,1],[.75,.25],3),([-1,1],[.5,.5],2),([-1,0,2],[.25,.5,.25],4)]:
    mu=sum(x*p for x,p in zip(population,weights))
    sig2=sum((x-mu)**2*p for x,p in zip(population,weights))
    mu3=sum((x-mu)**3*p for x,p in zip(population,weights))
    mu4=sum((x-mu)**4*p for x,p in zip(population,weights))
    sample_states=[]
    for indices in product(range(len(population)),repeat=n):
        xs=[population[i] for i in indices];prob=math.prod(weights[i] for i in indices)
        sample_states.append((prob,mean(xs),variance(xs)))
    ev=sum(p*v for p,m,v in sample_states)
    varv=sum(p*(v-ev)**2 for p,m,v in sample_states)
    covmv=sum(p*(m-mu)*(v-ev) for p,m,v in sample_states)
    assert math.isclose(ev,sig2,abs_tol=1e-12)
    assert math.isclose(varv,(mu4-(n-3)/(n-1)*sig2**2)/n,abs_tol=1e-12)
    assert math.isclose(covmv,mu3/n,abs_tol=1e-12)
assert .5!=.5*.5  # Rademacher n=2: {mean=0} equals {S^2=2}.
for p in [.2,.5,.8]:
    n=5;law=binomial_law(n,p);info=n/(p*(1-p));a=p*(1-p)/n
    scores=[(k-n*p)/(p*(1-p)) for k in range(n+1)]
    curvature=[-k/(p*p)-(n-k)/(1-p)**2 for k in range(n+1)]
    assert math.isclose(sum(w*u*u for w,u in zip(law,scores)),info)
    assert math.isclose(-sum(w*h for w,h in zip(law,curvature)),info)
    assert sum(w*(k/n-p-a*u)**2 for k,w,u in zip(range(n+1),law,scores))<1e-28
# Noninjective invariance: eta=p(1-p) has two preimages. Enumerate the
# profile likelihood without treating eta as a one-to-one reparameterization.
likelihood=lambda p:p**8*(1-p)**2
eta_values=[i/200 for i in range(51)]
profiles=[]
for eta in eta_values:
    root=math.sqrt(max(0,.25-eta))
    profiles.append(max(likelihood(.5-root),likelihood(.5+root)))
assert math.isclose(eta_values[profiles.index(max(profiles))],.16)
assert math.isclose(max(profiles),likelihood(.8),rel_tol=1e-12)
# Contingency tables: derive the fitted multinomial tangent projection with an
# actual full-rank Jacobian, independently of just counting parameters.
row_probs=[.2,.3,.5];col_probs=[.4,.6]
cell_probs=[a*b for a in row_probs for b in col_probs]
jacobian=[]
for i,j in product(range(3),range(2)):
    jacobian.append([col_probs[j]*((i==k)-(i==2)) for k in range(2)]+[row_probs[i]*(1 if j==0 else -1)])
weighted=[[v/math.sqrt(p) for v in row] for p,row in zip(cell_probs,jacobian)]
info=matmul_check(transpose_check(weighted),weighted)
tangent=matmul_check(matmul_check(weighted,inverse_check(info)),transpose_check(weighted))
residual=[[(i==j)-math.sqrt(cell_probs[i]*cell_probs[j])-tangent[i][j] for j in range(6)] for i in range(6)]
assert math.isclose(sum(residual[i][i] for i in range(6)),2,abs_tol=1e-12)
for i,j in product(range(6),repeat=2):
    ri,ci=divmod(i,2);rj,cj=divmod(j,2)
    expected=((ri==rj)-math.sqrt(row_probs[ri]*row_probs[rj]))*((ci==cj)-math.sqrt(col_probs[ci]*col_probs[cj]))
    assert math.isclose(residual[i][j],expected,abs_tol=1e-12)
    assert math.isclose(sum(residual[i][k]*residual[k][j] for k in range(6)),residual[i][j],abs_tol=1e-12)
# Fixed-row sampling: check the exact pooled-residual identity for unequal row
# sizes; it is a different covariance/projection from a single multinomial.
counts=[[5,4,8],[5,5,13],[11,3,17]]
sizes=[sum(row) for row in counts];n_table=sum(sizes);p_common=[.1,.2,.7]
z=[[(o-ni*p)/math.sqrt(ni*p) for o,p in zip(row,p_common)] for ni,row in zip(sizes,counts)]
s=[math.sqrt(ni/n_table) for ni in sizes]
pooled=[sum(row[j] for row in counts)/n_table for j in range(3)]
for i,j in product(range(3),repeat=2):
    projected=z[i][j]-s[i]*sum(s[k]*z[k][j] for k in range(3))
    actual=(counts[i][j]-sizes[i]*pooled[j])/math.sqrt(sizes[i]*p_common[j])
    assert math.isclose(projected,actual,abs_tol=1e-12)
pearson_ind=sum((o-e)**2/e for row,erow in zip([[18,12],[14,16],[8,12]],[[15,15],[15,15],[10,10]]) for o,e in zip(row,erow))
pearson_hom=sum((o-e)**2/e for row in [[12,6,2],[4,6,10]] for o,e in zip(row,[8,6,6]))
assert math.isclose(pearson_ind,32/15)
assert math.isclose(pearson_hom,28/3)
assert math.isclose(math.exp(-pearson_ind/2),.3441537868654124,abs_tol=1e-12)
assert math.isclose(math.exp(-pearson_hom/2),.009403562551495206,abs_tol=1e-12)
# Fisher's conditional test: enumerate small margin configurations using exact
# fractions, including ties. Test superuniformity at every attainable p-value.
for total in range(1,13):
    for row_size,col_size in product(range(total+1),repeat=2):
        support=range(max(0,row_size+col_size-total),min(row_size,col_size)+1)
        law={a:Fraction(math.comb(col_size,a)*math.comb(total-col_size,row_size-a),math.comb(total,row_size)) for a in support}
        assert sum(law.values())==1
        alternative={a:Fraction(math.comb(row_size,a)*math.comb(total-row_size,col_size-a),math.comb(total,col_size)) for a in support}
        assert law==alternative
        ordered={a:sum(w for w in law.values() if w<=mass) for a,mass in law.items()}
        for alpha in set(ordered.values()):
            assert sum(mass for a,mass in law.items() if ordered[a]<=alpha)<=alpha
assert [Fraction(math.comb(2,a)*math.comb(5,3-a),math.comb(7,3)) for a in range(3)]==[Fraction(2,7),Fraction(4,7),Fraction(1,7)]
# Gaussian integral and moments: quadrature of the density and its shifted
# powers verifies normalization, recurrence examples and Var(X^2) independently.
normal_density=lambda z:math.exp(-z*z/2)/math.sqrt(2*math.pi)
for power,expected in [(0,1),(2,1),(4,3),(6,15),(8,105)]:
    assert math.isclose(simpson_check(lambda z:z**power*normal_density(z),-12,12),expected,abs_tol=1e-8)
assert math.isclose(simpson_check(lambda z:(2+3*z)**4*normal_density(z),-12,12),475,abs_tol=1e-8)
assert math.isclose(simpson_check(lambda z:((2+3*z)**2-13)**2*normal_density(z),-12,12),306,abs_tol=1e-8)
assert math.isclose(1/(-math.log(.6)),1.9576151889712174,abs_tol=1e-12)
assert math.isclose(math.exp(2*math.log(.6)),.36,abs_tol=1e-12)
# Balanced two-way ANOVA: recover the five subspaces from nested least-squares
# design matrices and check their projection algebra in exact arithmetic.
factor_rows=list(product(range(2),range(3),range(2)))
x0=[[1] for i,j,k in factor_rows]
xa=[[1,(-1 if i==0 else 1)] for i,j,k in factor_rows]
xb=[[1,(j==0)-(j==2),(j==1)-(j==2)] for i,j,k in factor_rows]
xcell=[[1,(-1 if i==0 else 1),(j==0)-(j==2),(j==1)-(j==2),(-1 if i==0 else 1)*((j==0)-(j==2)),(-1 if i==0 else 1)*((j==1)-(j==2))] for i,j,k in factor_rows]
def hat_check(design):
    xt=transpose_check(design)
    return matmul_check(matmul_check(design,inverse_check(matmul_check(xt,design))),xt)
def subtract_matrix_check(a,b):
    return [[v-w for v,w in zip(row,other)] for row,other in zip(a,b)]
h0=hat_check(x0);ha=hat_check(xa);hb=hat_check(xb);hc=hat_check(xcell)
identity=[[Fraction(i==j) for j in range(12)] for i in range(12)]
pa=subtract_matrix_check(ha,h0);pb=subtract_matrix_check(hb,h0)
pab=[[hc[i][j]-ha[i][j]-hb[i][j]+h0[i][j] for j in range(12)] for i in range(12)]
pe=subtract_matrix_check(identity,hc)
projectors=[h0,pa,pb,pab,pe]
for proj,rank in zip(projectors,[1,1,2,2,6]):
    assert proj==transpose_check(proj)==matmul_check(proj,proj)
    assert sum(proj[i][i] for i in range(12))==rank
for i,j in product(range(12),repeat=2):
    assert sum(proj[i][j] for proj in projectors)==identity[i][j]
for left,right in product(range(5),repeat=2):
    if left!=right:assert matmul_check(projectors[left],projectors[right])==[[0]*12 for _ in range(12)]
def two_way_sums_check(data):
    a=len(data);b=len(data[0]);r=len(data[0][0])
    grand=mean(x for row in data for cell in row for x in cell)
    rows=[mean(x for cell in row for x in cell) for row in data]
    cols=[mean(x for row in data for x in row[j]) for j in range(b)]
    cells=[[mean(cell) for cell in row] for row in data]
    return [b*r*sum((x-grand)**2 for x in rows),a*r*sum((x-grand)**2 for x in cols),r*sum((cells[i][j]-rows[i]-cols[j]+grand)**2 for i,j in product(range(a),range(b))),sum((x-cells[i][j])**2 for i,j in product(range(a),range(b)) for x in data[i][j])]
assert two_way_sums_check([[[4,6],[4,6]],[[2,4],[10,12]]])==[8,32,32,8]
single=[[[1],[3],[5]],[[4],[4],[6]]]
single_sums=two_way_sums_check(single)
for actual,expected in zip(single_sums,[25/6,28/3,4/3,0]):
    assert math.isclose(actual,expected,abs_tol=1e-12)
assert math.isclose(sum(single_sums),89/6)
# Enumerate finite independent unit-variance errors. Normality is unnecessary
# for expected mean squares; this does NOT claim independent projections here.
all_sums=[]
for signs in product([-1,1],repeat=8):
    data=[[[7+(-1 if i==0 else 1)+(-2 if j==0 else 2)+3*((-1)**(i+j))+signs[4*i+2*j+k] for k in range(2)] for j in range(2)] for i in range(2)]
    all_sums.append(two_way_sums_check(data))
assert [mean(row[j] for row in all_sums) for j in range(4)]==[9,33,73,4]
contaminated=[]
interaction=[[1,-2,1],[-1,2,-1]]
for signs in product([-1,1],repeat=6):
    data=[[[3+i+2*j+interaction[i][j]+signs[3*i+j]] for j in range(3)] for i in range(2)]
    contaminated.append(two_way_sums_check(data)[2]/2)
assert math.isclose(mean(contaminated),7,abs_tol=1e-12)
# Chapter-three CDF differences: exact cumulative sums from a nonindependent
# discrete law, and a coordinatewise-monotone candidate with negative mass.
joint_mass=[[Fraction(1,5),Fraction(3,10)],[Fraction(2,5),Fraction(1,10)]]
def joint_cdf_check(x,y):
    return sum(joint_mass[i][j] for i,j in product(range(2),repeat=2) if i<=x and j<=y)
for i,j in product(range(2),repeat=2):
    assert joint_cdf_check(i,j)-joint_cdf_check(i-1,j)-joint_cdf_check(i,j-1)+joint_cdf_check(i-1,j-1)==joint_mass[i][j]
for x,y in product([-.2,0,.5,1,2],repeat=2):
    value=joint_cdf_check(x,y);fx=joint_cdf_check(x,2);fy=joint_cdf_check(2,y)
    assert max(0,fx+fy-1)<=value<=min(fx,fy)
assert Fraction(1)-Fraction(7,10)-Fraction(7,10)+Fraction(1,10)==Fraction(-3,10)
# Integrate the actual bivariate density over x; check conditional first and
# second moments without assuming its factorization into the claimed answer.
for rho,y in product([-.8,0,.5,.8],[-2.,0.,2.]):
    mu1,mu2,sd1,sd2=1.,-.5,1.5,2.
    s2=1-rho*rho;v=(y-mu2)/sd2
    def bivariate_density_check(x):
        u=(x-mu1)/sd1
        return math.exp(-(u*u-2*rho*u*v+v*v)/(2*s2))/(2*math.pi*sd1*sd2*math.sqrt(s2))
    marginal=normal_density(v)/sd2
    expected_mu=mu1+rho*sd1*v;expected_var=sd1*sd1*s2
    assert math.isclose(simpson_check(bivariate_density_check,-25,25),marginal,abs_tol=1e-10)
    assert math.isclose(simpson_check(lambda x:x*bivariate_density_check(x),-25,25)/marginal,expected_mu,abs_tol=1e-9)
    assert math.isclose(simpson_check(lambda x:(x-expected_mu)**2*bivariate_density_check(x),-25,25)/marginal,expected_var,abs_tol=1e-9)
p_abs=simpson_check(normal_density,-1,1)
assert math.isclose(p_abs,.6826894921370859,abs_tol=1e-12)
assert math.isclose(p_abs*p_abs,.4660649426743922,abs_tol=1e-12)
# Characteristic function of (Z,SZ), averaged over the two independent signs,
# differs from that of a Gaussian vector with its identical covariance I.
assert .5*(1+math.exp(-2))>math.exp(-1)
# Normal interval examples: invert an independent analytic F(2,2) CDF, and
# check reciprocal intervals by transforming the parameter, not the data order.
f22_cdf=lambda x:x/(1+x)
assert f22_cdf(Fraction(1,19))==Fraction(1,20)
assert f22_cdf(Fraction(19))==Fraction(19,20)
assert [Fraction(4,19),Fraction(76)]==[Fraction(4)/19,Fraction(4)/Fraction(1,19)]
assert [Fraction(1,76),Fraction(19,4)]==[1/Fraction(76),1/Fraction(4,19)]
assert Fraction(4*4+6*9,10)==7
assert 7*(Fraction(1,5)+Fraction(1,7))==Fraction(12,5)
halfwidth=2.228139*math.sqrt(12/5)
assert math.isclose(halfwidth,3.451818096014099,abs_tol=1e-12)
assert math.isclose(3-halfwidth,-.45182,abs_tol=5e-6)
# Welch matching: integrate two chi-square laws, combine raw moments of the
# independent scaled variables, then recover the central moment by expansion.
raw_chi=[]
for df in [4,7]:
    density=lambda u:u**(df/2-1)*math.exp(-u/2)/(2**(df/2)*math.gamma(df/2))
    raw_chi.append([simpson_check(lambda u:u**k*density(u),0,120) for k in range(4)])
    assert math.isclose(raw_chi[-1][0],1,abs_tol=1e-7)
raw_w=[]
for k in range(4):
    raw_w.append(sum(math.comb(k,j)*raw_chi[0][j]*raw_chi[1][k-j]/7**(k-j) for j in range(k+1)))
m_w=raw_w[1];var_w=raw_w[2]-m_w*m_w
third_w=raw_w[3]-3*m_w*raw_w[2]+2*m_w**3
assert math.isclose(m_w,5,abs_tol=1e-6)
assert math.isclose(var_w,58/7,abs_tol=1e-5)
assert math.isclose(third_w,1576/49,abs_tol=1e-4)
assert Fraction(25)/(Fraction(16,4)+Fraction(1,7))==Fraction(175,29)
assert Fraction(1576,49)>Fraction(6728,245)
for n1,n2,v1,v2 in product([2,3,5,10],[2,4,8],[.01,.5,2,20],[.02,1,3,50]):
    nu_hat=(v1+v2)**2/(v1*v1/(n1-1)+v2*v2/(n2-1))
    assert min(n1-1,n2-1)-1e-10<=nu_hat<=n1+n2-2+1e-10
# Even at equal sample sizes and a common population variance, realized
# unequal sample variances make the plug-in Welch df smaller than pooled df.
assert (4+1)**2/(16/4+1/4)<8
# Conditional bootstrap: enumerate all labeled resamples rather than only
# evaluating a formula. Repeated original values keep their original masses.
bootstrap_data=[Fraction(1),Fraction(2),Fraction(5)]
states_boot=list(product(range(3),repeat=3))
means_boot=[mean(bootstrap_data[i] for i in state) for state in states_boot]
variances_boot=[variance(bootstrap_data[i] for i in state) for state in states_boot]
weights_boot=[[state.count(i) for i in range(3)] for state in states_boot]
assert mean(means_boot)==Fraction(8,3)
assert mean((v-Fraction(8,3))**2 for v in means_boot)==Fraction(26,27)
assert mean(variances_boot)==Fraction(26,9)
assert mean(variances_boot)-variance(bootstrap_data)==Fraction(-13,9)
assert sum(row==[2,1,0] for row in weights_boot)==3
assert mean(row[0] for row in weights_boot)==1
assert mean(Fraction((row[0]-1)**2) for row in weights_boot)==Fraction(2,3)
assert mean(Fraction((row[0]-1)*(row[1]-1)) for row in weights_boot)==Fraction(-1,3)
weight_counts={tuple(row):weights_boot.count(row) for row in weights_boot}
for weights,count in weight_counts.items():
    assert count==math.factorial(3)//math.prod(math.factorial(w) for w in weights)
# Two independent simulations: their B-1 sample variance is conditionally
# unbiased, but its square root has strict downward bias in this finite law.
variance_estimates=[(a-b)**2/2 for a,b in product(means_boot,repeat=2)]
assert mean(variance_estimates)==Fraction(26,27)
assert mean(math.sqrt(v) for v in variance_estimates)<math.sqrt(26/27)
assert mean((a+b)/2 for a,b in product(means_boot,repeat=2))==Fraction(8,3)
assert mean(((a+b)/2-Fraction(8,3))**2 for a,b in product(means_boot,repeat=2))==Fraction(13,27)
duplicate_means=[mean(Fraction([1,1,5][i]) for i in state) for state in states_boot]
assert mean(duplicate_means)==Fraction(7,3)
# Conditional hit counts are exactly binomial; adding one changes expectation
# and cannot turn an approximate fitted model into an exact null distribution.
hit_prob=Fraction(1,5);b_sim=4
hit_law=[Fraction(math.comb(b_sim,k))*hit_prob**k*(1-hit_prob)**(b_sim-k) for k in range(b_sim+1)]
assert sum(w*Fraction(k,b_sim) for k,w in enumerate(hit_law))==hit_prob
assert sum(w*(Fraction(k,b_sim)-hit_prob)**2 for k,w in enumerate(hit_law))==hit_prob*(1-hit_prob)/b_sim
assert sum(w*Fraction(k+1,b_sim+1) for k,w in enumerate(hit_law))==Fraction(1+b_sim*hit_prob,b_sim+1)
# Moment shape counterexample: exact finite law, including its unique median
# and mode. Zero skewness is weaker than reflection of the whole distribution.
shape_values=[-2,-1,1,3]
shape_weights=[Fraction(1,5),Fraction(1,4),Fraction(1,2),Fraction(1,20)]
shape_moments=[sum(w*x**k for x,w in zip(shape_values,shape_weights)) for k in range(5)]
assert shape_moments==[1,0,2,0,8]
assert shape_weights[0]!=0 and 2 not in shape_values
assert sum(w for x,w in zip(shape_values,shape_weights) if x<1)==Fraction(9,20)
assert sum(w for x,w in zip(shape_values,shape_weights) if x<=1)==Fraction(19,20)
assert shape_values[shape_weights.index(max(shape_weights))]==1
# Three-time autocorrelation incompatibility: a negative exact quadratic form
# supplies a direct impossibility proof, beyond checking pointwise bounds.
candidate_r=lambda t:max(1-Fraction(t*t,4),0)
coeff=[Fraction(1),Fraction(-3,2),Fraction(1)]
quadratic=sum(coeff[i]*coeff[j]*candidate_r(i-j) for i,j in product(range(3),repeat=2))
assert quadratic==Fraction(-1,4)
assert candidate_r(2)<2*candidate_r(1)**2-1==Fraction(1,8)
for times in [[0,.2,1,3],[0,math.pi/3,2*math.pi/3],[0,-1,2,4]]:
    coefficients=[i-1.2 for i in range(len(times))]
    values=[sum(c*(a*math.cos(t)+b*math.sin(t)) for c,t in zip(coefficients,times)) for a,b in product([-1,1],repeat=2)]
    covariance_form=sum(a*b*math.cos(t-s) for a,t in zip(coefficients,times) for b,s in zip(coefficients,times))
    assert math.isclose(mean(v*v for v in values),covariance_form,abs_tol=1e-12)
    assert covariance_form>=-1e-12
# Finite-window spectrum: independently integrate the triangularly weighted
# exponential correlation and compare a closed-form complex antiderivative.
import cmath
for window,omega in product([.5,2,10],[0,.7,3]):
    finite_integral=simpson_check(lambda t:8*(1-t/window)*math.exp(-2*t)*math.cos(omega*t),0,window)
    rate=2+1j*omega
    finite_closed=8*(1/rate-(1-cmath.exp(-rate*window))/(window*rate*rate)).real
    spectrum=16/(4+omega*omega)
    assert math.isclose(finite_integral,finite_closed,abs_tol=1e-10)
    assert finite_integral>=-1e-12
    assert abs(spectrum-finite_closed)<=2/window+1e-12
# Arrival-time proof: mix finite-window uniform order densities over the
# actual Poisson total, then compare with the interarrival-product density.
for lam,k,tk,horizon in [(2,2,.75,2),(1.7,3,1.4,3),(.5,1,2,5),(3,4,.8,1.2)]:
    mixture=0.
    for total in range(k,100):
        poisson_weight=math.exp(-lam*horizon)*(lam*horizon)**total/math.factorial(total)
        first_k_density=math.factorial(total)/math.factorial(total-k)*(horizon-tk)**(total-k)/horizon**total
        mixture+=poisson_weight*first_k_density
    assert math.isclose(mixture,lam**k*math.exp(-lam*tk),abs_tol=1e-11)
    gaps=[tk/k]*k
    product_density=math.prod(lam*math.exp(-lam*e) for e in gaps)
    assert math.isclose(mixture,product_density,abs_tol=1e-11)
assert math.isclose(simpson_check(lambda t:.75*t*(2-t),0,2),1,abs_tol=1e-12)
interarrival_tail=simpson_check(lambda e:2*math.exp(-2*e),.5,25)*simpson_check(lambda e:2*math.exp(-2*e),1,25)
assert math.isclose(interarrival_tail,math.exp(-3),abs_tol=1e-11)
joint_arrival_tail=simpson_check(lambda e:2*math.exp(-2*e)*math.exp(-2*(1-e)),.5,1)+math.exp(-2)
assert math.isclose(joint_arrival_tail,2*math.exp(-2),abs_tol=1e-12)
assert not math.isclose(joint_arrival_tail,3*math.exp(-3),abs_tol=1e-3)
# General expectations retain atoms; integrate directly over the original U,
# independently of the mixture formula displayed in the card.
mixed_first=simpson_check(lambda u:max(0,u)/4,-2,2)
mixed_second=simpson_check(lambda u:max(0,u)**2/4,-2,2)
assert math.isclose(mixed_first,.5,abs_tol=1e-12)
assert math.isclose(mixed_second,2/3,abs_tol=1e-12)
assert math.isclose(mixed_second-mixed_first**2,5/12,abs_tol=1e-12)
for value in [Fraction(1,100),Fraction(1,3),Fraction(17,5),Fraction(20)]:
    simple_values=[min(Fraction(n),Fraction((2**n*value).__floor__(),2**n)) for n in range(1,11)]
    assert all(a<=b<=value for a,b in zip(simple_values,simple_values[1:]))
# Exact finite conditional law: build means/variances from its joint masses,
# then verify total variance and the full prediction error decomposition.
conditional_values=[-2,1,4]
conditional_mass=[[Fraction(1,12),Fraction(2,12),Fraction(1,12)],
                  [Fraction(2,12),Fraction(1,12),Fraction(5,12)]]
groups=[sum(row) for row in conditional_mass]
conditional_means=[sum(p*x for p,x in zip(row,conditional_values))/q for row,q in zip(conditional_mass,groups)]
conditional_vars=[sum(p*(x-m)**2 for p,x in zip(row,conditional_values))/q for row,q,m in zip(conditional_mass,groups,conditional_means)]
all_mean=sum(p*x for row in conditional_mass for p,x in zip(row,conditional_values))
all_variance=sum(p*(x-all_mean)**2 for row in conditional_mass for p,x in zip(row,conditional_values))
within=sum(q*v for q,v in zip(groups,conditional_vars))
between=sum(q*(m-all_mean)**2 for q,m in zip(groups,conditional_means))
assert all_variance==within+between
for predictor in product([Fraction(-1),Fraction(1,3),Fraction(2),Fraction(5)],repeat=2):
    direct_loss=sum(p*(x-a)**2 for row,a in zip(conditional_mass,predictor) for p,x in zip(row,conditional_values))
    assert direct_loss==within+sum(q*(m-a)**2 for q,m,a in zip(groups,conditional_means,predictor))
    assert sum(p*(x-m)*a for row,m,a in zip(conditional_mass,conditional_means,predictor) for p,x in zip(row,conditional_values))==0
# Triangular joint density: numerical conditional and marginal integrations,
# not just evaluating the already simplified variance formula.
for y in [.1,.4,.95]:
    mass=simpson_check(lambda x:2,0,y)
    cmean=simpson_check(lambda x:2*x,0,y)/mass
    cvar=simpson_check(lambda x:2*(x-cmean)**2,0,y)/mass
    assert math.isclose(cmean,y/2,abs_tol=1e-12)
    assert math.isclose(cvar,y*y/12,abs_tol=1e-12)
tri_mean=simpson_check(lambda x:x*2*(1-x),0,1)
tri_var=simpson_check(lambda x:(x-tri_mean)**2*2*(1-x),0,1)
tri_within=simpson_check(lambda y:y*y/12*2*y,0,1)
tri_between=simpson_check(lambda y:(y/2-tri_mean)**2*2*y,0,1)
assert math.isclose(tri_mean,1/3,abs_tol=1e-12)
assert math.isclose(tri_var,1/18,abs_tol=1e-12)
assert math.isclose(tri_within,1/24,abs_tol=1e-12)
assert math.isclose(tri_between,1/72,abs_tol=1e-12)
assert math.isclose(tri_var,tri_within+tri_between,abs_tol=1e-12)
# Nonlinear predictor: integrate the actual two-noise mixture, compare its
# true risks and check that linear covariance vanishes despite dependence.
def noisy_uniform_moment(func):
    return sum(simpson_check(lambda y:func(y*y+noise,y)/4,-1,1) for noise in [-1,1])
assert math.isclose(noisy_uniform_moment(lambda x,y:x),1/3,abs_tol=1e-12)
assert math.isclose(noisy_uniform_moment(lambda x,y:(x-1/3)**2),49/45,abs_tol=1e-12)
assert math.isclose(noisy_uniform_moment(lambda x,y:x*y),0,abs_tol=1e-12)
assert math.isclose(noisy_uniform_moment(lambda x,y:(x-y*y)**2),1,abs_tol=1e-12)
for a,b in [(-1,.5),(1/3,0),(2,-2)]:
    risk=noisy_uniform_moment(lambda x,y:(x-a-b*y)**2)
    assert math.isclose(risk,49/45+(a-1/3)**2+b*b/3,abs_tol=1e-11)
# Independently expand linear forms of independent standard normals. This
# integrates monomials using one-dimensional even moments, without using
# the fourth-order pairing identity being checked.
def normal_linear_product(rows):
    degree=len(rows);dimension=len(rows[0]);result=0.
    for coordinates in product(range(dimension),repeat=degree):
        coefficient=math.prod(row[j] for row,j in zip(rows,coordinates))
        moment=1
        for j in range(dimension):
            power=coordinates.count(j)
            if power%2:moment=0;break
            moment*=math.prod(range(1,power,2))
        result+=coefficient*moment
    return result
for rows in [[[1,0],[.5,math.sqrt(3)/2],[1,0],[.5,math.sqrt(3)/2]],
             [[1,2,0],[0,-1,1],[2,0,-1],[1,1,1]],
             [[0,0],[1,2],[1,2],[1,-1]]]:
    cov=lambda i,j:sum(a*b for a,b in zip(rows[i],rows[j]))
    expected_pairs=cov(0,1)*cov(2,3)+cov(0,2)*cov(1,3)+cov(0,3)*cov(1,2)
    assert math.isclose(normal_linear_product(rows),expected_pairs,abs_tol=1e-12)
rho=.5
rows_ar=[[1.,0,0,0,0,0,0]]
for k in range(1,7):
    row=[rho*v for v in rows_ar[-1]]
    row[k]=math.sqrt(1-rho*rho)
    rows_ar.append(row)
for h,u in product(range(3),range(5)):
    actual_fourth=normal_linear_product([rows_ar[0],rows_ar[h],rows_ar[u],rows_ar[u+h]])
    product_covariance=actual_fourth-rho**(2*h)
    k_formula=rho**(2*u)+rho**(abs(u+h)+abs(u-h))
    assert math.isclose(product_covariance,k_formula,abs_tol=1e-12)
for window in [.01,.2,1,5]:
    gaussian_square_error=simpson_check(lambda u:16*(window-u)*math.exp(-6*u)/window**2,0,window)
    exact_error=8/(3*window)-4*(-math.expm1(-6*window))/(9*window**2)
    assert math.isclose(gaussian_square_error,exact_error,abs_tol=1e-10)
    assert 0<gaussian_square_error<=8/(3*window)
# A common random amplitude leaves a nondecaying fourth-order component,
# even though the original second-order covariance decays exponentially.
amplitude_squares=[Fraction(1),Fraction(3)]
assert mean(amplitude_squares)==2 and mean(a*a for a in amplitude_squares)==5
assert mean((a-2)**2 for a in amplitude_squares)==1
for lag in [0,.3,2]:
    fourth=5*(1+2*math.exp(-2*lag))
    assert math.isclose(fourth-4,1+10*math.exp(-2*lag),abs_tol=1e-12)
for window in [1,3,10]:
    mse_mixture=simpson_check(lambda u:2*(window-u)*(1+10*math.exp(-2*u))/window**2,0,window)
    closed=1+10/window-5*(-math.expm1(-2*window))/window**2
    assert math.isclose(mse_mixture,closed,abs_tol=1e-10)
    assert mse_mixture>1
# Confirm code fences remain code rather than being interpreted as mathematics.
r_page=(ROOT/'chapter-11.html').read_text(encoding='utf-8')
assert r_page.count('<pre><code class="language-r">')==6
assert 'boxplot.stats(x)$stats' in r_page
assert 'CODETOKEN' not in r_page
print(f'PASS: {len(pages)} pages, {links} local links/anchors, {sum(x.math for x in pages.values())} rendered formulas; {len(concepts)} concepts, {len(exercises)} exercises, {len(exams)} x 100-point exams; mathematical spot checks.')
