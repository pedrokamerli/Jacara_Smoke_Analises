"""Altera apenas o limite de upload do vhost privado e preserva o restante."""
from datetime import datetime, timezone
from pathlib import Path
import re
import shutil
import subprocess

path=Path("/opt/evolync/nginx/runtime/evolync.conf")
start,end="# BEGIN JACARE PRIVATE MANAGED","# END JACARE PRIVATE MANAGED"
original=path.read_text()
begin,finish=original.index(start),original.index(end)+len(end)
block=original[begin:finish]
if "server_name jacare.pedromerli.com;" not in block: raise ValueError("Vhost privado divergente")
block,count=re.subn(r"client_max_body_size\s+\S+;","client_max_body_size 200m;",block)
if count!=1: raise ValueError("Limite do vhost privado ausente ou ambíguo")
replacement=original[:begin]+block+original[finish:]
backup=path.with_name("evolync.conf.backup-jacare-upload-"+datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
shutil.copy2(path,backup)
path.write_text(replacement)
try:
    for command in (["docker","exec","evolync_nginx","nginx","-t"],["docker","exec","evolync_nginx","nginx","-s","reload"]):
        if subprocess.run(command,capture_output=True).returncode: raise RuntimeError("Nginx recusou configuração")
except Exception:
    path.write_text(original)
    subprocess.run(["docker","exec","evolync_nginx","nginx","-s","reload"],capture_output=True)
    raise
print("Limite de upload privado ajustado; demais vhosts e proxy preservados.")
