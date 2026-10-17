"""Prove LF/CRLF input checkouts produce the same generated site and version."""
from pathlib import Path
import re
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
ARTIFACTS=ROOT/'artifacts'
ARTIFACTS.mkdir(exist_ok=True)
inputs=[ROOT/'build.py']+[p for folder in ['assets','data'] for p in (ROOT/folder).rglob('*') if p.is_file()]
with tempfile.TemporaryDirectory(prefix='newline-build-',dir=ARTIFACTS) as name:
    target=Path(name).resolve()
    assert target.is_relative_to(ARTIFACTS.resolve())
    for label,ending in [('lf',b'\n'),('crlf',b'\r\n')]:
        copy=target/label
        for source in inputs:
            destination=copy/source.relative_to(ROOT)
            destination.parent.mkdir(parents=True,exist_ok=True)
            content=source.read_bytes()
            if source.suffix!='.png':
                content=content.replace(b'\r\n',b'\n').replace(b'\n',ending)
            destination.write_bytes(content)
        subprocess.run([sys.executable,str(copy/'build.py')],check=True,capture_output=True)
    outputs=[p.relative_to(target/'lf') for p in (target/'lf').glob('*.html')]+[Path('assets/index-data.js')]
    for path in outputs:
        a=(target/'lf'/path).read_text(encoding='utf-8')
        b=(target/'crlf'/path).read_text(encoding='utf-8')
        assert a==b, f'Line-ending-dependent build: {path}'
    version=re.search(r'assets/site.js\?v=([a-f0-9]+)',(target/'lf/index.html').read_text(encoding='utf-8')).group(1)
print(f'PASS: LF/CRLF builds match across {len(outputs)} generated files; version {version}')
