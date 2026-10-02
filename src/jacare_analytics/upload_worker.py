"""Worker sem rede: processa um pacote por vez e publica somente snapshot auditado."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import signal
import subprocess
import sys
import time
import duckdb
from datetime import date
from pathlib import Path

from .pipeline import run_pipeline, audit_warehouse
from .runtime_config import load_runtime_config
from .upload_jobs import atomic_json, cleanup_inputs, job_path, list_jobs, load_bundle, set_status, timestamp


def freeze_forecast(data: Path, manifest: dict):
    config=load_runtime_config(data.parent,{"JACARE_PUBLIC_MODE":"false"})
    payload=config.resolve_artifact(manifest["forecast_metrics"]).read_bytes()
    archive=data/"forecast_archive"
    archive.mkdir(exist_ok=True,mode=0o700)
    name=hashlib.sha256(manifest["run_id"].encode()).hexdigest()+".json"
    target=archive/name
    preserved={"run_id":manifest["run_id"],"source_end":manifest["source_end"],"series_sha256":manifest["series_sha256"],"metrics_sha256":hashlib.sha256(payload).hexdigest(),"metrics":json.loads(payload)}
    if target.exists():
        if json.loads(target.read_text())["metrics_sha256"]!=preserved["metrics_sha256"]:
            raise ValueError("Previsão arquivada não pode ser substituída")
    else:
        with target.open("x",encoding="utf-8") as handle: json.dump(preserved,handle,ensure_ascii=False,allow_nan=False)
        target.chmod(0o400)


def publish_snapshot(work: Path, data: Path, manifest: dict, previous: dict, job_id: str):
    from scripts.package_private_data import portable_warehouse
    # Evitar substituir histórico cumulativo por um mês isolado.
    if (date.fromisoformat(manifest["source_start"])>date.fromisoformat(previous["source_start"])
        or date.fromisoformat(manifest["source_end"])<date.fromisoformat(previous["source_end"])
        or manifest["quality"]["paid_orders"]<previous["quality"]["paid_orders"]):
        raise ValueError("Pacote não preserva o histórico anterior")
    with duckdb.connect(str(data.parent/previous["warehouse"]),read_only=True) as db:
        before=db.execute("select sale_date,paid_orders,has_source_records from analytics.fct_daily_sales").df()
    with duckdb.connect(str(work/manifest["warehouse"]),read_only=True) as db:
        after=db.execute("select sale_date,paid_orders,has_source_records from analytics.fct_daily_sales").df()
    check=before.loc[before.has_source_records].merge(after,on="sale_date",how="left",suffixes=("_before","_after"))
    if (~check.has_source_records_after.fillna(False).astype(bool)).any() or (check.paid_orders_after<check.paid_orders_before).any():
        raise ValueError("Pacote remove dias ou reduz pedidos históricos; exige revisão técnica")
    run=manifest["run_id"]
    destination=data/"runs"/run
    destination.mkdir(parents=True,exist_ok=False,mode=0o700)
    source=json.loads((work/manifest["source_manifest"]).read_text())
    portable=destination/"jacare_analytics.duckdb"
    portable_warehouse(work/manifest["warehouse"],portable)
    if audit_warehouse(portable,source)!=manifest["quality"]: raise ValueError("Snapshot não reconciliou")
    for key in ("analysis_report","forecast_metrics","quality_report"):
        target=data.parent/manifest[key]
        target.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        shutil.copyfile(work/manifest[key],target)
    analysis=(data.parent/manifest["analysis_report"]).with_name("analysis_results.json")
    shutil.copyfile((work/manifest["analysis_report"]).with_name("analysis_results.json"),analysis)
    source_target=data.parent/manifest["source_manifest"]
    if manifest.get('customer_directory'):
        target=data.parent/manifest['customer_directory']
        target.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        shutil.copyfile(work/manifest['customer_directory'],target)
    atomic_json(source_target,{"dataset_kind":"real_confidential","run_id":run,"originals_retained":False,"source_sha256":{key:entry["sha256"] for key,entry in source["sources"].items()}},mode=0o400)
    manifest={**manifest,"sources":{},"deployment_storage":"materialized_dbt_snapshot","import_job_id":job_id}
    # Artefatos imutáveis; leitores existentes continuam usando seus arquivos antigos.
    for member in destination.rglob("*"): member.chmod(0o700 if member.is_dir() else 0o400)
    freeze_forecast(data,previous)
    atomic_json(data/"current_run.json",manifest,mode=0o400)
    return manifest


def process_job(template: Path, jobs: Path, data: Path, job_id: str, secret_file: Path, *, raise_errors=False):
    path=job_path(jobs,job_id)
    set_status(path,state="running",step="Validando pacote e integridade")
    try:
        previous=json.loads((data/"current_run.json").read_text())
        freeze_forecast(data,previous)
        bundle,cutoff=load_bundle(path)
        work=path/"work"
        work.mkdir(mode=0o700)
        for name in ("warehouse","sql","config"):
            shutil.copytree(template/name,work/name)
        # Mantém o HMAC original estável, só no worker; nunca gravado na fila ou na imagem.
        os.environ["JACARE_ANALYTICS_HMAC_KEY"]=secret_file.read_text().strip()
        manifest=run_pipeline(bundle,work,cutoff,progress=lambda step:set_status(path,step=step))
        set_status(path,step="Validando snapshot e preservando previsão anterior")
        manifest=publish_snapshot(work,data,manifest,previous,job_id)
        set_status(path,state="complete",step="Atualização aprovada e disponível",run_id=manifest["run_id"],source_end=manifest["source_end"])
    except Exception as error:
        # Uma falha posterior à troca atômica não deve anunciar que a base antiga está ativa.
        current=json.loads((data/"current_run.json").read_text())
        if current.get("import_job_id")==job_id:
            set_status(path,state="complete",step="Atualização aprovada e disponível",run_id=current["run_id"],source_end=current["source_end"])
        else:
            last=json.loads((path/"status.json").read_text())["step"]
            set_status(path,state="failed",error_code=type(error).__name__,failed_phase=last,step="Pacote não aprovado. Confira formatos, fontes obrigatórias e histórico cumulativo. A base anterior continua ativa.")
        if raise_errors: raise
    finally:
        os.environ.pop("JACARE_ANALYTICS_HMAC_KEY",None)
        cleanup_inputs(path)


def serve(template: Path, jobs: Path, data: Path, secret: Path):
    import fcntl
    jobs.mkdir(parents=True,exist_ok=True,mode=0o700)
    handle=(jobs/"worker.lock").open("a")
    fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
    # Interrupções não provocam publicação parcial nem repetição silenciosa.
    for job in list_jobs(jobs):
        if job["state"]=="running":
            path=job_path(jobs,job["job_id"])
            current=json.loads((data/"current_run.json").read_text())
            complete=current.get("import_job_id")==job["job_id"]
            set_status(path,state="complete" if complete else "failed",step="Atualização disponível" if complete else "Processamento interrompido; a base anterior foi preservada. Envie novamente.")
            cleanup_inputs(path)
    freeze_forecast(data,json.loads((data/"current_run.json").read_text()))
    while True:
        atomic_json(jobs/"heartbeat.json",{"at":timestamp()})
        queued=[job for job in list_jobs(jobs) if job["state"]=="queued"]
        if queued:
            job_id=queued[-1]["job_id"]
            child=subprocess.Popen([sys.executable,"-m","jacare_analytics.upload_worker","--job",job_id],start_new_session=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            started=time.monotonic()
            while child.poll() is None:
                atomic_json(jobs/"heartbeat.json",{"at":timestamp()})
                if time.monotonic()-started>1800:
                    os.killpg(child.pid,signal.SIGKILL)
                    child.wait()
                    break
                time.sleep(3)
            path=job_path(jobs,job_id)
            if json.loads((path/"status.json").read_text())["state"] in {"running","queued"}:
                current=json.loads((data/"current_run.json").read_text())
                complete=current.get("import_job_id")==job_id
                set_status(path,state="complete" if complete else "failed",step="Atualização disponível" if complete else "Processador interrompido ou tempo limite excedido; a base anterior foi preservada.")
                cleanup_inputs(path)
        time.sleep(3)


if __name__=="__main__":
    template=Path("/app")
    jobs=Path(os.environ.get("JACARE_IMPORT_QUEUE","/imports"))
    data=template/"data"
    secret=Path("/worker-secrets/hmac.key")
    if len(sys.argv)==3 and sys.argv[1]=="--job": process_job(template,jobs,data,sys.argv[2],secret)
    else: serve(template,jobs,data,secret)
