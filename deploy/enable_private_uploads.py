"""Configuração privada explícita, sem imprimir contas, tokens ou chaves."""
import os
import re
import shutil
import json
import sys
import tomllib
from pathlib import Path

base=Path("/opt/portfolio/jacare-analytics/private")
secret=base/"secrets.toml"
original=secret.read_text()
config=tomllib.loads(original)
if not config.get("access",{}).get("allowed_emails"):
    raise ValueError("Lista de contas autorizadas ausente")
backup=base/"secrets.uploads-v1.rollback.toml"
if not backup.exists():
    shutil.copy2(secret,backup)
    backup.chmod(0o400)
if len(sys.argv)==3 and sys.argv[1]=="--allow-email":
    email=sys.argv[2].strip().lower()
    if not re.fullmatch(r"[a-z0-9._+%-]+@[a-z0-9.-]+\.[a-z]{2,}",email): raise ValueError("Conta inválida")
    allowed=config["access"]["allowed_emails"]
    if email not in {value.strip().lower() for value in allowed}:
        allowed=[*allowed,email]
        original,count=re.subn(r"(?ms)^allowed_emails\s*=\s*\[[^\]]*\]", "allowed_emails = "+json.dumps(allowed),original)
        if count!=1 or tomllib.loads(original)["access"]["allowed_emails"]!=allowed:
            raise ValueError("Não foi possível validar as contas autorizadas")
if "uploads_for_all_allowed" in config["access"]:
    replacement,count=re.subn(r"(?m)^uploads_for_all_allowed\s*=.*$","uploads_for_all_allowed = true",original)
else:
    replacement,count=re.subn(r"(?m)^\[access\]\s*$","[access]\nuploads_for_all_allowed = true",original)
if count!=1 or tomllib.loads(replacement)["access"].get("uploads_for_all_allowed") is not True:
    raise ValueError("Configuração de upload não pôde ser validada")
secret.write_text(replacement)
os.chown(secret,10001,10001)
secret.chmod(0o400)
for name in ("imports","worker_secrets"):
    folder=base/name
    folder.mkdir(exist_ok=True,mode=0o700)
    os.chown(folder,10001,10001)
    folder.chmod(0o700)
key=base/"worker_secrets/hmac.key"
if not key.is_file() or key.is_symlink(): raise ValueError("Chave de pseudonimização ausente")
os.chown(key,10001,10001)
key.chmod(0o400)
print("Contas autorizadas validadas e upload habilitado. Backup privado preservado; nenhuma identidade ou credencial impressa.")
