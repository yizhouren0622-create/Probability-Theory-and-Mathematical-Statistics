"""Run the exact six chapter 11 code blocks, without third-party R packages.

Usage: python scripts/check-r-examples.py --rscript Rscript --report data/r-verification.json
For a WebR host, --driver FILE emits the same base-R driver. After executing it,
--output FILE --runtime DESCRIPTION imports its stdout and checks the success markers.
Plots execute on pdf(NULL): this verifies calls and numbers, not chart appearance.
"""
import argparse
import hashlib
import json
import re
import subprocess
import tempfile
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHECKS = {
    'r-basics': '''
z <- c(n = sum(ok), mean = mean(x[ok]), variance = var(x[ok]))
stopifnot(isTRUE(all.equal(unname(z), c(3, 4, 4))))
z
''',
    'r-boxplot': '''
z <- boxplot.stats(x)
stopifnot(identical(as.numeric(z$stats), c(1, 2, 3, 4, 4)),
          identical(as.numeric(z$out), 20))
c(lower_whisker=z$stats[1], lower_hinge=z$stats[2], median=z$stats[3],
  upper_hinge=z$stats[4], upper_whisker=z$stats[5], outlier=z$out)
''',
    'r-hypothesis-tests': '''
w <- t.test(x, y); p <- t.test(x, y, paired=TRUE)
vx <- sum((x-mean(x))^2)/(length(x)-1)
vy <- sum((y-mean(y))^2)/(length(y)-1)
tw <- (mean(x)-mean(y))/sqrt(vx/length(x)+vy/length(y))
dfw <- (vx/5+vy/5)^2/((vx/5)^2/4+(vy/5)^2/4)
stopifnot(abs(w$statistic-tw)<1e-12, abs(w$parameter-dfw)<1e-12,
          abs(p$statistic-0.8/sqrt(1.2/5))<1e-12, p$parameter==4)
c(welch_t=unname(w$statistic), welch_df=unname(w$parameter), welch_p=w$p.value,
  paired_t=unname(p$statistic), paired_df=unname(p$parameter), paired_p=p$p.value)
''',
    'r-anova': '''
a <- summary(fit)[[1]]
stopifnot(all(a$Df==c(1,4)), max(abs(a$`Sum Sq`-c(13.5,4)))<1e-12,
          abs(a$`F value`[1]-13.5)<1e-12)
c(factor_ss=a$`Sum Sq`[1], residual_ss=a$`Sum Sq`[2],
  factor_df=a$Df[1], residual_df=a$Df[2], F=a$`F value`[1], p=a$`Pr(>F)`[1])
''',
    'r-regression': '''
ci <- predict(fit, data.frame(x=1), interval="confidence")
pi <- predict(fit, data.frame(x=1), interval="prediction")
# With one residual degree of freedom the t critical value has this closed form.
critical <- 1/tan(base::pi*0.025)
stopifnot(max(abs(coef(fit)-c(7/6,1/2)))<1e-12,
          max(abs(ci-c(5/3, 5/3-critical/sqrt(18), 5/3+critical/sqrt(18))))<1e-8,
          max(abs(pi-c(5/3, 5/3-critical*sqrt(2/9), 5/3+critical*sqrt(2/9))))<1e-8)
c(intercept=unname(coef(fit)[1]), slope=unname(coef(fit)[2]), fit=ci[1],
  confidence_lower=ci[2], confidence_upper=ci[3],
  prediction_lower=pi[2], prediction_upper=pi[3])
''',
    'r-bootstrap': '''
stopifnot(length(tb)==2000, all(is.finite(tb)), all(tb>=min(x) & tb<=max(x)),
          sd(tb)>1.0, sd(tb)<1.25, abs(mean(tb)-4)<0.1)
# The simulation SE is not asserted to equal its exact conditional limit.
q <- quantile(tb, c(.025,.975))
c(B=length(tb), boot_mean=mean(tb), boot_se=sd(tb),
  percentile_lower=unname(q[1]), percentile_upper=unname(q[2]), exact_variance=20/16)
''',
}


def examples():
    chapter = next(c for c in json.loads((ROOT/'data/course.json').read_text(encoding='utf-8')) if c['id']==11)
    result = {}
    for section in chapter['sections']:
        for concept in section['concepts']:
            blocks = re.findall(r'```r\n(.*?)\n```', concept['statement'], re.S)
            assert len(blocks)==1, concept['id']
            code = blocks[0]
            result[concept['id']] = {'code':code, 'sha256':hashlib.sha256(code.encode()).hexdigest()}
    assert set(result)==set(CHECKS)
    return result


def make_driver(blocks):
    q = lambda s: json.dumps(s, ensure_ascii=True)
    lines = ['options(width=120, digits=10)', 'cat("R_VERSION|", R.version.string, "\\n", sep="")',
             'cat("R_PLATFORM|", R.version$platform, "\\n", sep="")',
             'cat("R_RNG|", paste(RNGkind(), collapse=","), "\\n", sep="")',
             'run_example <- function(id, code, check) {',
             '  env <- new.env(parent=globalenv())',
             '  grDevices::pdf(file=NULL)',
             '  on.exit(grDevices::dev.off())',
             '  cat("BEGIN|", id, "\\n", sep="")',
             '  source(textConnection(code), local=env, print.eval=TRUE)',
             '  metrics <- eval(parse(text=check), envir=env)',
             '  stopifnot(is.numeric(metrics), all(is.finite(metrics)))',
             '  for (key in names(metrics)) cat("METRIC|", id, "|", key, "|", sprintf("%.17g", metrics[[key]]), "\\n", sep="")',
             '  cat("PASS|", id, "\\n", sep="")', '}']
    for cid, block in blocks.items():
        lines.append(f'run_example({q(cid)}, {q(block["code"])}, {q(CHECKS[cid])})')
    lines.append('cat("ALL_SIX_R_EXAMPLES_PASSED\\n")')
    return '\n'.join(lines)+'\n'


def make_report(output, blocks, runtime):
    assert 'ALL_SIX_R_EXAMPLES_PASSED' in output, 'R did not complete all examples'
    entries = {}
    for cid, block in blocks.items():
        assert f'PASS|{cid}' in output, cid
        metrics = {k:float(v) for k,v in re.findall(rf'^METRIC\|{re.escape(cid)}\|([^|]+)\|([^\r\n]+)', output, re.M)}
        assert metrics, cid
        entries[cid] = {'codeSha256':block['sha256'], 'status':'executed_and_checked', 'metrics':metrics}
    field = lambda key: re.search(rf'^{key}\|([^\r\n]+)', output, re.M).group(1)
    return {'runDate':date.today().isoformat(), 'runtime':runtime,
            'rVersion':field('R_VERSION'), 'platform':field('R_PLATFORM'), 'rng':field('R_RNG'),
            'scope':'Six uncommented base-R examples; plots use pdf(NULL). No chart appearance audit or boot::boot package execution.',
            'examples':entries}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--driver', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--rscript', default='Rscript')
    parser.add_argument('--runtime', default='Native Rscript')
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    blocks = examples()
    driver = make_driver(blocks)
    if args.driver:
        args.driver.write_text(driver, encoding='utf-8')
        print(f'Wrote driver containing {len(blocks)} exact code blocks')
        return
    if args.output:
        output = args.output.read_text(encoding='utf-8')
    else:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/'check.R'
            path.write_text(driver, encoding='utf-8')
            output = subprocess.run([args.rscript, '--vanilla', str(path)], check=True,
                                    capture_output=True, text=True, encoding='utf-8').stdout
    report = make_report(output, blocks, args.runtime)
    if args.report:
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__=='__main__':
    main()
