"""Integração real em mounts de QA, nunca no volume de produção."""
import hashlib
import json
import time
import subprocess
import re
from unittest.mock import patch
from datetime import date
from pathlib import Path

import duckdb
from jacare_analytics.source_files import SourceFile
from jacare_analytics.upload_jobs import atomic_json, submit_job, timestamp
from jacare_analytics.upload_worker import process_job

assert Path("/qa_upload_test_marker").is_file(),"Somente container isolado de QA"
data=Path("/app/data")
jobs=Path("/imports")
inputs=Path("/qa-inputs")
previous=json.loads((data/"current_run.json").read_text())
original_metrics=(Path("/app")/previous["forecast_metrics"]).read_bytes()
source=json.loads((inputs/"sources.json").read_text())
bundle={key:SourceFile(entry["name"],(inputs/entry["stored"]).read_bytes()) for key,entry in source.items()}
now=time.time()
claims={"iss":"https://accounts.google.com","sub":"qa-subject","email":"qa@example.com","email_verified":True,"iat":now-1,"exp":now+1800}
access={"allowed_emails":["qa@example.com"],"uploads_for_all_allowed":True}
atomic_json(jobs/"heartbeat.json",{"at":timestamp()})
job=submit_job(jobs,bundle,date.fromisoformat(previous["cutoff"]),claims,access)
real_subprocess_run=subprocess.run
def diagnose(*args,**kwargs):
    result=real_subprocess_run(*args,**kwargs)
    if result.returncode:
        message=(result.stdout or "")+(result.stderr or "")
        causes=[word for word in ("Permission denied","Read-only file system","HTTP Error","Failed to download","No module named","No such file or directory","can't start new thread","Operation not permitted") if word.lower() in message.lower()]
        print("Categorias de falha dbt: "+", ".join(causes))
        diagnostic=re.sub(r"[a-fA-F0-9]{32,}","[hash]",message[-3500:])
        diagnostic=re.sub(r"[\w.+-]+@[\w.-]+","[email]",diagnostic)
        print("Diagnóstico dbt (sem registros de origem): "+diagnostic)
    return result
with patch("jacare_analytics.pipeline.subprocess.run",side_effect=diagnose):
    process_job(Path("/app"),jobs,data,job,Path("/worker-secrets/hmac.key"),raise_errors=True)
status=json.loads((jobs/job/"status.json").read_text())
assert status["state"]=="complete",status["step"]
current=json.loads((data/"current_run.json").read_text())
assert current["run_id"]!=previous["run_id"]
assert current["quality"]==previous["quality"]
assert current["import_job_id"]==job
assert current["sources"]=={}
with duckdb.connect(str(Path("/app")/current["warehouse"]),read_only=True) as db:
    assert db.execute("select count(*) from information_schema.tables where table_schema='analytics' and table_type='VIEW'").fetchone()[0]==0
archive=list((data/"forecast_archive").glob("*.json"))
assert len(archive)==1
assert json.loads(archive[0].read_text())["metrics_sha256"]==hashlib.sha256(original_metrics).hexdigest()
assert not list((jobs/job).glob("*.bin")) and not (jobs/job/"work").exists()
assert len(json.loads((Path("/app")/current["analysis_report"]).with_name("analysis_results.json").read_text()))==15
print("Upload real de QA aprovado: preparação, dbt, auditoria, 15 respostas, ML, publicação atômica e previsão original preservada. Originais transitórios removidos, nenhum resultado impresso.")
