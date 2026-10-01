"""Replica snapshot privado para QA sem alterar o dataset em produção."""
import os
import shutil
from pathlib import Path

base=Path("/opt/portfolio/jacare-analytics/private")
source=(base/"data").resolve()
if not source.is_relative_to(base/"datasets") or not (source/"current_run.json").is_file():
    raise ValueError("Snapshot de origem fora do diretório esperado")
qa=base/"qa_uploads_v1"
qa.mkdir(mode=0o700,exist_ok=False)
shutil.copytree(source,qa/"data")
(qa/"imports").mkdir(mode=0o700)
(qa/"marker").write_text("isolated upload QA")
for parent in (qa,base/"qa_uploads_inputs",base/"worker_secrets"):
    if parent.is_symlink() or not parent.resolve().is_relative_to(base): raise ValueError("Permissões fora do diretório privado")
    for path in [parent,*parent.rglob("*")]:
        if path.is_symlink(): raise ValueError("Link não permitido no QA")
        os.chown(path,10001,10001)
        path.chmod(0o700 if path.is_dir() else 0o600)
(base/"worker_secrets/hmac.key").chmod(0o400)
print("Snapshot isolado de QA preparado; produção preservada.")
