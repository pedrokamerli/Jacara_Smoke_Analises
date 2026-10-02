"""Cópia isolada da produção para homologar atualização sem tocar no ativo."""
import os,shutil
from pathlib import Path
base=Path('/opt/portfolio/jacare-analytics/private')
source=(base/'data').resolve()
if not source.is_relative_to(base/'datasets'): raise ValueError('Origem fora do diretório privado')
qa=base/'september_qa_v1'
qa.mkdir(mode=0o700,exist_ok=False)
shutil.copytree(source,qa/'data')
(qa/'imports').mkdir(mode=0o700)
(qa/'marker').write_text('isolated upload QA')
for path in [qa,*qa.rglob('*')]:
    if path.is_symlink(): raise ValueError('Links não permitidos no QA')
    os.chown(path,10001,10001)
    path.chmod(0o700 if path.is_dir() else 0o600)
raw=base/'dashboard att setembro.rar'
os.chown(raw,10001,10001)
raw.chmod(0o400)
print('QA privado preparado; produção não alterada')
