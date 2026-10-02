"""Atualização restrita aos dois serviços Jacaré, com rollback preservado."""
from pathlib import Path
import argparse
import shutil
import subprocess

BASE=Path('/opt/portfolio/jacare-analytics/private')
DEMO=Path('/opt/portfolio/jacare-analytics/releases/20261001T114846Z')

parser=argparse.ArgumentParser()
parser.add_argument('--revision', choices=['v1','v2'], default='v1')
revision=parser.parse_args().revision

def update(path, project, old, new, services):
    content=path.read_text()
    if old not in content: raise ValueError('Imagem anterior inesperada; revisar antes de publicar')
    backup=path.with_name(path.name+'.before-story-'+revision)
    with backup.open('x') as handle: handle.write(content)
    backup.chmod(0o400)
    path.write_text(content.replace(old,new))
    subprocess.run(['docker','compose','-p',project,'-f',str(path),'config','--quiet'],check=True)
    try:
        subprocess.run(['docker','compose','-p',project,'-f',str(path),'up','-d','--no-build',*services],check=True)
    except Exception:
        shutil.copyfile(backup,path)
        subprocess.run(['docker','compose','-p',project,'-f',str(path),'up','-d','--no-build',*services],check=True)
        raise

backup_manifest=BASE/('manifest.before-story-'+revision+'.json')
with backup_manifest.open('x') as handle:
    handle.write((BASE/'data/current_run.json').read_text())
backup_manifest.chmod(0o400)
subprocess.run(['docker','tag','jacare-analytics-private:story-'+revision,'jacare-analytics-demo:story-'+revision],check=True)
old_private='jacare-analytics-private:september-v2' if revision=='v1' else 'jacare-analytics-private:story-v1'
old_demo='jacare-analytics-demo:release' if revision=='v1' else 'jacare-analytics-demo:story-v1'
update(BASE/'compose.private.yaml','jacare-private',old_private,'jacare-analytics-private:story-'+revision,['jacare-private','jacare-worker'])
update(DEMO/'compose.yaml','jacare-demo',old_demo,'jacare-analytics-demo:story-'+revision,['jacare-demo'])
print('Apresentação atualizada; configurações anteriores preservadas. Dados públicos continuam sintéticos.')
