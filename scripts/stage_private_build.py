"""Monta contexto de build só com código autorizado, sem dados ou segredos."""
from pathlib import Path
import shutil

ROOT=Path(__file__).resolve().parents[1]

def stage(target: Path):
    if not target.resolve().is_relative_to((ROOT/"data/private/build").resolve()):
        raise ValueError("Contexto fora da pasta privada de build")
    target.mkdir(parents=True,exist_ok=False)
    paths=[ROOT/"app/streamlit_app.py",ROOT/"config/business_calendar.json",ROOT/"warehouse/dbt_project.yml",ROOT/"warehouse/profiles.example.yml",ROOT/"scripts/package_private_data.py"]
    for directory,pattern in [("src/jacare_analytics","*.py"),("warehouse/models","*.sql"),("warehouse/models","*.yml"),("warehouse/tests","*.sql"),("warehouse/macros","*.sql"),("sql/business","*.sql")]:
        paths.extend((ROOT/directory).rglob(pattern))
    for source in paths:
        if source.is_symlink(): raise ValueError("Não incluir links no build")
        destination=target/source.relative_to(ROOT)
        destination.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(source,destination)
    shutil.copyfile(ROOT/"deploy/Dockerfile.private",target/"Dockerfile.private")
    shutil.copyfile(ROOT/"deploy/private.dockerignore",target/".dockerignore")
    print("Contexto preparado somente com código, SQL e configuração pública do calendário.")

if __name__=="__main__":
    import sys
    stage(Path(sys.argv[1]))
