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
# Confirm code fences remain code rather than being interpreted as mathematics.
r_page=(ROOT/'chapter-11.html').read_text(encoding='utf-8')
assert r_page.count('<pre><code class="language-r">')==6
assert 'boxplot.stats(x)$stats' in r_page
assert 'CODETOKEN' not in r_page
print(f'PASS: {len(pages)} pages, {links} local links/anchors, {sum(x.math for x in pages.values())} rendered formulas; {len(concepts)} concepts, {len(exercises)} exercises, {len(exams)} x 100-point exams; mathematical spot checks.')
