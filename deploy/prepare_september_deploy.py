"""Registra rollback privado antes de atualizar serviços e dados."""
import json,subprocess
from pathlib import Path
base=Path('/opt/portfolio/jacare-analytics/private')
web=subprocess.check_output(['docker','inspect','-f','{{.Config.Image}}','jacare_private'],text=True).strip()
worker=subprocess.check_output(['docker','inspect','-f','{{.Config.Image}}','jacare_worker'],text=True).strip()
if web!=worker or web!='jacare-analytics-private:uploads-v1': raise ValueError('Estado anterior inesperado; revisar antes de publicar')
snapshot=base/'september-v1.before.json'
with snapshot.open('x') as handle: handle.write((base/'data/current_run.json').read_text())
snapshot.chmod(0o400)
compose=(base/'compose.private.yaml').read_text()
assert compose.count('jacare-analytics-private:september-v1')==2
rollback=base/'compose.september-v1.validated-rollback.yaml'
with rollback.open('x') as handle: handle.write(compose.replace('jacare-analytics-private:september-v1',web))
rollback.chmod(0o400)
print('Rollback de imagem e manifesto anterior registrados privadamente')
