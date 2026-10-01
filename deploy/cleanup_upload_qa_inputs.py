"""Remove somente cópias transitórias de fontes criadas para a homologação."""
from pathlib import Path
import shutil
import subprocess

target=Path("/opt/portfolio/jacare-analytics/private/qa_uploads_inputs")
if target.is_symlink() or target.resolve()!=target or target.parent!=Path("/opt/portfolio/jacare-analytics/private"):
    raise ValueError("Destino de limpeza inválido")
for name in ("jacare_upload_pipeline_qa_v1","jacare_upload_pipeline_qa_v2","jacare_upload_pipeline_qa_v3","jacare_upload_pipeline_qa_v4","jacare_upload_pipeline_qa_v5"):
    state=subprocess.check_output(["docker","inspect","-f","{{.State.Status}}",name],text=True).strip()
    if state not in {"exited","created"}: raise ValueError("Homologação ainda em execução")
if target.is_dir(): shutil.rmtree(target)
print("Cópias transitórias de fontes de QA removidas. Fontes originais locais e snapshots aprovados preservados.")
