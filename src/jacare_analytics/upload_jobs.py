"""Fila privada em disco: nenhum caminho de destino vem do arquivo enviado."""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import uuid
from datetime import date, datetime, timezone
from pathlib import Path

from .authentication import authorized_import_admin
from .prepare_social_sources import METRIC_PREFIXES
from .source_files import SourceFile, MAX_FILE_BYTES, MAX_UPLOAD_BYTES, logical_name, validate_payload

REQUIRED = frozenset({"orders", "items"})
ROLES = {"orders":"Pedidos do PDV", "items":"Itens vendidos", "appdelivery":"AppDelivery / MenuDino", "food99":"99Food", "meta_ads":"Meta Ads (opcional)", "ifood_report":"Relatório adicional iFood (opcional)", **{"instagram_"+key:"Instagram: "+key for key in METRIC_PREFIXES}}
ROLES['customers']='Cadastro de clientes (nomes somente no privado)'
ACTIVE = {"queued", "running"}


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def atomic_json(path: Path, payload: dict, *, mode=0o600):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary=path.with_name(path.name+"."+uuid.uuid4().hex+".tmp")
    with temporary.open("x", encoding="utf-8") as handle:
        json.dump(payload,handle,ensure_ascii=False,allow_nan=False)
        handle.flush()
        os.fsync(handle.fileno())
    temporary.chmod(mode)
    os.replace(temporary,path)


def job_path(root: Path, job_id: str) -> Path:
    if not isinstance(job_id,str) or not re.fullmatch(r"[0-9a-f]{32}",job_id):
        raise ValueError("Identificador de importação inválido")
    path=root/job_id
    if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
        raise ValueError("Importação fora da fila permitida")
    return path


def list_jobs(root: Path) -> list[dict]:
    if not root.is_dir(): return []
    jobs=[]
    for path in root.iterdir():
        if not re.fullmatch(r"[0-9a-f]{32}",path.name) or path.is_symlink(): continue
        status=path/"status.json"
        if status.is_file() and not status.is_symlink():
            jobs.append(json.loads(status.read_text(encoding="utf-8")))
    return sorted(jobs,key=lambda job:job["created_at"],reverse=True)


def submit_job(root: Path, bundle: dict[str,SourceFile], cutoff: date, claims: dict, access: dict, *, now=None) -> str:
    # Revalidar no envio, não confiar em menu oculto ou session_state.
    if not authorized_import_admin(claims,access,now):
        raise PermissionError("Somente uma conta com permissão de upload pode atualizar os dados")
    return _enqueue_job(root,bundle,cutoff,actor=claims['sub'])


def _enqueue_job(root,bundle,cutoff,*,actor):
    """Uso interno: UI já autorizada ou operador via SSH. Não é uma rota pública."""
    if cutoff>date.today(): raise ValueError("A data completa não pode estar no futuro")
    if REQUIRED-bundle.keys(): raise ValueError("Envie todas as fontes obrigatórias do pacote consolidado")
    if set(bundle)-ROLES.keys(): raise ValueError("Fonte não autorizada")
    if len(bundle)>20 or sum(len(item.payload) for item in bundle.values())>MAX_UPLOAD_BYTES:
        raise ValueError("O pacote ultrapassa os limites de importação")
    for key,item in bundle.items():
        if not item.payload or len(item.payload)>MAX_FILE_BYTES or logical_name(item.name)!=key:
            raise ValueError("Uma fonte é inválida ou excede 100 MiB")
        validate_payload(item.name,item.payload)
    root.mkdir(parents=True,exist_ok=True,mode=0o700)
    lock=root/"submit.lock"
    descriptor=os.open(lock,os.O_CREAT|os.O_RDWR,0o600)
    try:
        if os.name=="nt":
            import msvcrt
            if os.fstat(descriptor).st_size==0: os.write(descriptor,b"0")
            os.lseek(descriptor,0,os.SEEK_SET)
            msvcrt.locking(descriptor,msvcrt.LK_NBLCK,1)
        else:
            import fcntl
            fcntl.flock(descriptor,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except OSError:
        os.close(descriptor)
        raise ValueError("Outro envio está sendo registrado; tente novamente")
    try:
        if any(job["state"] in ACTIVE for job in list_jobs(root)):
            raise ValueError("Já existe uma importação em andamento")
        # Não aceitar envios se o worker não estiver saudável.
        heartbeat=root/"heartbeat.json"
        if not heartbeat.exists() or (datetime.now(timezone.utc)-datetime.fromisoformat(json.loads(heartbeat.read_text())["at"])).total_seconds()>45:
            raise ValueError("Processador indisponível; os dados atuais continuam protegidos")
        if shutil.disk_usage(root).free<2*1024**3: raise ValueError("Espaço insuficiente para atualizar com segurança")
        job_id=uuid.uuid4().hex
        path=job_path(root,job_id)
        path.mkdir(mode=0o700)
        files={}
        for index,(key,item) in enumerate(sorted(bundle.items())):
            stored=f"source_{index:02d}.bin"
            target=path/stored
            with target.open("xb") as handle: handle.write(item.payload)
            target.chmod(0o600)
            files[key]={"stored":stored,"name":item.name,"sha256":item.sha256}
        atomic_json(path/"request.json",{"job_id":job_id,"cutoff":cutoff.isoformat(),"files":files})
        atomic_json(path/"status.json",{"job_id":job_id,"state":"queued","created_at":timestamp(),"step":"Na fila", "actor_sha256":hashlib.sha256(actor.encode()).hexdigest()})
        return job_id
    except Exception:
        if "path" in locals() and path.exists() and not (path/"status.json").exists(): cleanup_inputs(path)
        raise
    finally:
        if os.name=="nt":
            os.lseek(descriptor,0,os.SEEK_SET)
            msvcrt.locking(descriptor,msvcrt.LK_UNLCK,1)
        os.close(descriptor)


def load_bundle(path: Path) -> tuple[dict[str,SourceFile],date]:
    request=json.loads((path/"request.json").read_text(encoding="utf-8"))
    if request["job_id"]!=path.name or not REQUIRED<=request["files"].keys() or set(request["files"])-ROLES.keys():
        raise ValueError("Solicitação inválida")
    bundle={}
    total=0
    for key,entry in request["files"].items():
        if not re.fullmatch(r"source_[0-9]{2}\.bin",entry["stored"]): raise ValueError("Arquivo inválido")
        source=path/entry["stored"]
        if source.is_symlink() or source.stat().st_size>MAX_FILE_BYTES: raise ValueError("Arquivo inválido")
        payload=source.read_bytes()
        total+=len(payload)
        if total>MAX_UPLOAD_BYTES or hashlib.sha256(payload).hexdigest()!=entry["sha256"] or logical_name(entry["name"])!=key:
            raise ValueError("Falha na integridade das fontes")
        bundle[key]=SourceFile(entry["name"],payload)
        validate_payload(entry["name"],payload)
    cutoff=date.fromisoformat(request["cutoff"])
    if cutoff>date.today(): raise ValueError("Corte futuro inválido")
    return bundle,cutoff


def set_status(path: Path, **updates):
    status=json.loads((path/"status.json").read_text(encoding="utf-8"))
    atomic_json(path/"status.json",{**status,**updates,"updated_at":timestamp()})


def cleanup_inputs(path: Path):
    # Somente filhos conhecidos de uma importação UUID, nunca um caminho fornecido pelo usuário.
    if not re.fullmatch(r"[0-9a-f]{32}",path.name) or path.is_symlink(): raise ValueError("Limpeza fora da importação")
    for member in path.glob("source_[0-9][0-9].bin"):
        if not member.is_symlink(): member.unlink()
    workspace=path/"work"
    if workspace.is_dir() and not workspace.is_symlink() and workspace.resolve().parent==path.resolve():
        shutil.rmtree(workspace)
    (path/"request.json").unlink(missing_ok=True)
