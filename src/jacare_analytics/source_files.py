"""Leitura de fontes autorizadas, locais ou enviadas ao painel, sem extração de ZIPs."""

from __future__ import annotations

import hashlib
import io
import os
import re
import shutil
import subprocess
import tempfile
import threading
import zlib
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .inventory import _archive_name
from .prepare_delivery_sources import APPDELIVERY_MEMBER, NINEFOOD_MEMBER
from .prepare_social_sources import METRIC_PREFIXES, _plain
from .profile_sales import ITEMS_MEMBER, ORDERS_MEMBER

META_MEMBER = "04_Relatorio_Meta_Atualizado_ate_19-08-2026.xlsx"
IFOOD_MEMBER = "01_Analise_Jacare_Tratada.xlsx"
MAX_FILE_BYTES = 100 * 1024 * 1024
MAX_UPLOAD_BYTES = 200 * 1024 * 1024
IGNORED_DIRS = {".git", ".venv", "venv", "data", "__pycache__", "target", "dbt_packages", ".idea"}


@dataclass(frozen=True)
class SourceFile:
    name: str
    payload: bytes

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.payload).hexdigest()


def logical_name(name: str, *, updated_dates: bool = True) -> str | None:
    name = Path(name.replace("\\", "/")).name
    exact = {ORDERS_MEMBER: "orders", ITEMS_MEMBER: "items", APPDELIVERY_MEMBER: "appdelivery", NINEFOOD_MEMBER: "food99", META_MEMBER: "meta_ads", IFOOD_MEMBER: "ifood_report"}
    if name in exact:
        return exact[name]
    # Datas da exportação podem mudar; contrato da planilha continua sendo validado.
    for pattern,key in [(r"01_Todos_os_pedidos_.*\.xlsx","orders"), (r"02_Historico_Itens_Vendidos_.*\.xlsx","items"), (r"Pedidos_AppDelivery_.*\.xlsx","appdelivery"), (r"_Dados do pedido\(.*\)\.xlsx","food99"), (r"04_Relatorio_Meta_Atualizado_ate_.*\.xlsx","meta_ads")]:
        if updated_dates and re.fullmatch(pattern,name,re.IGNORECASE): return key
    plain = _plain(name)
    if updated_dates and plain.endswith('.xlsx'):
        if plain.startswith('todos os pedidos'): return 'orders'
        if plain.startswith('historico_itens_vendidos'): return 'items'
        if plain == '99food.xlsx': return 'food99'
        if plain == 'relatorio ifood.xlsx': return 'ifood_report'
        if plain.startswith('lista-clientes'): return 'customers'
    if plain.endswith(".csv") and "insta" in plain:
        for metric, prefix in METRIC_PREFIXES.items():
            if prefix in plain:
                return f"instagram_{metric}"
    return None


def _add(bundle: dict[str, SourceFile], name: str, payload: bytes, *, updated_dates=False) -> None:
    key = logical_name(name,updated_dates=updated_dates)
    if key is None:
        return
    validate_payload(name,payload)
    candidate = SourceFile(Path(name.replace("\\", "/")).name, payload)
    if key in bundle and bundle[key].sha256 != candidate.sha256:
        raise ValueError(f"Mais de uma versão da fonte {key}; selecione apenas o pacote oficial atual.")
    bundle[key] = candidate


def validate_payload(name: str, payload: bytes) -> None:
    if not payload or len(payload)>MAX_FILE_BYTES:
        raise ValueError("Uma fonte está vazia ou excede 100 MiB")
    if name.lower().endswith(".xlsx"):
        if not zipfile.is_zipfile(io.BytesIO(payload)): raise ValueError("Planilha XLSX inválida")
        with zipfile.ZipFile(io.BytesIO(payload)) as book:
            members=book.infolist()
            if len(members)>2000 or sum(x.file_size for x in members)>500*1024*1024:
                raise ValueError("Planilha excede limite de descompressão")
            names={x.filename for x in members}
            if not {"[Content_Types].xml","xl/workbook.xml"}<=names or any("vbaproject" in x.lower() for x in names):
                raise ValueError("Planilha inválida ou com macros não permitidas")
    elif name.lower().endswith(".csv"):
        if payload.startswith(b"PK") or b"<!DOCTYPE" in payload[:4096].upper(): raise ValueError("CSV inválido")
    else: raise ValueError("Tipo de fonte não autorizado")


def collect_local(root: Path) -> dict[str, SourceFile]:
    root = root.resolve()
    if not root.is_dir():
        raise ValueError("Pasta de fontes não encontrada.")
    bundle: dict[str, SourceFile] = {}
    for directory, dirs, files in os.walk(root):
        dirs[:] = [name for name in dirs if name not in IGNORED_DIRS]
        for name in sorted(files):
            if logical_name(name,updated_dates=False) is None:
                continue
            path = Path(directory) / name
            if path.stat().st_size > MAX_FILE_BYTES:
                raise ValueError("Uma fonte selecionada ultrapassa 100 MiB.")
            _add(bundle, name, path.read_bytes())
    return bundle


def _rar_members(payload: bytes):
    """RAR simples, sem senha/volumes/links; bsdtar lê para stdout, nunca extrai caminhos."""
    import rarfile
    tool=shutil.which('bsdtar') or (shutil.which('tar') if os.name=='nt' else None)
    if not tool: raise ValueError('Leitor RAR indisponível. Envie ZIP ou as planilhas diretamente.')
    with tempfile.TemporaryDirectory(prefix='jacare-rar-') as directory:
        archive_path=Path(directory)/'package.rar'
        archive_path.write_bytes(payload)
        try:
            with rarfile.RarFile(archive_path,errors='strict') as archive:
                if archive.needs_password() or len(archive.volumelist())!=1:
                    raise ValueError('RAR com senha ou múltiplos volumes não é aceito. Envie ZIP.')
                members=archive.infolist()
                if len(members)>2000 or sum(x.file_size for x in members)>500*1024*1024:
                    raise ValueError('RAR excede os limites de arquivos ou descompressão')
                for member in members:
                    name=member.filename
                    parts=name.replace('\\','/').split('/')
                    if '..' in parts or name.startswith(('/','\\')) or ':' in name or member.is_symlink() or getattr(member,'file_redir',None):
                        raise ValueError('RAR contém caminho ou link não permitido')
                    if member.is_dir(): continue
                    if member.file_size>MAX_FILE_BYTES: raise ValueError('Fonte RAR excede 100 MiB')
                    if logical_name(name) is None and not name.lower().endswith(('.zip','.rar')): continue
                    # bsdtar usa padrões: escapar metacaracteres evita concatenar membros.
                    pattern=''.join('\\'+c if c in '*?[]\\' else c for c in name)
                    process=subprocess.Popen([tool,'-xOf',str(archive_path),'--',pattern],stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
                    timer=threading.Timer(30,process.kill)
                    timer.start()
                    try:
                        content=process.stdout.read(min(member.file_size,MAX_FILE_BYTES)+1)
                        if len(content)>member.file_size: process.kill()
                        code=process.wait(timeout=5)
                    finally:
                        timer.cancel()
                        if process.poll() is None: process.kill(); process.wait()
                        process.stdout.close()
                    if code or len(content)!=member.file_size:
                        raise ValueError('RAR não pôde ser lido com segurança. Converta para ZIP.')
                    if member.CRC is not None and zlib.crc32(content)!=member.CRC:
                        raise ValueError('Integridade do RAR inválida')
                    yield name,content
        except rarfile.Error as error:
            raise ValueError('RAR inválido ou não suportado; envie ZIP.') from error


def collect_uploads(files: Iterable[tuple[str, bytes]], *, updated_dates=False) -> dict[str, SourceFile]:
    bundle: dict[str, SourceFile] = {}
    total_uploaded = 0
    expanded_bytes = 0
    members_seen = 0

    def read_rar(payload,depth=0):
        nonlocal expanded_bytes,members_seen
        if depth>3: raise ValueError('Pacote excede limite de arquivos aninhados')
        for name,content in _rar_members(payload):
            members_seen+=1
            expanded_bytes+=len(content)
            if members_seen>2000 or expanded_bytes>500*1024*1024: raise ValueError('Pacote excede limites de descompressão')
            if name.lower().endswith('.zip'): read_zip(content,depth+1)
            elif name.lower().endswith('.rar'): read_rar(content,depth+1)
            else: _add(bundle,name,content,updated_dates=updated_dates)

    def read_zip(payload: bytes, depth: int = 0) -> None:
        nonlocal expanded_bytes, members_seen
        if depth > 3:
            raise ValueError("O pacote excede o limite de ZIPs aninhados.")
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            for member in archive.infolist():
                members_seen+=1
                if members_seen>2000: raise ValueError("O pacote contém arquivos demais")
                parts=member.filename.replace("\\","/").split("/")
                if ".." in parts or member.filename.startswith(("/","\\")) or ":" in member.filename or (member.external_attr>>16)&0o170000==0o120000:
                    raise ValueError("O ZIP contém um caminho ou link não permitido")
                if member.is_dir():
                    continue
                name = _archive_name(member.filename)
                selected = logical_name(name,updated_dates=updated_dates) is not None
                nested = name.lower().endswith((".zip",".rar"))
                if not selected and not nested:
                    continue
                if member.file_size > MAX_FILE_BYTES:
                    raise ValueError("Uma fonte dentro do ZIP ultrapassa 100 MiB.")
                expanded_bytes += member.file_size
                if expanded_bytes > 500 * 1024 * 1024:
                    raise ValueError("O pacote excede o limite de descompressão de 500 MiB.")
                content = archive.read(member)
                if nested:
                    (read_rar if name.lower().endswith('.rar') else read_zip)(content, depth + 1)
                else:
                    _add(bundle, name, content,updated_dates=updated_dates)

    for name, payload in files:
        total_uploaded += len(payload)
        if total_uploaded > MAX_UPLOAD_BYTES:
            raise ValueError("Selecione até 200 MiB de arquivos por atualização.")
        if name.lower().endswith(".zip"):
            read_zip(payload)
        elif name.lower().endswith('.rar'):
            read_rar(payload)
        else:
            _add(bundle, name, payload,updated_dates=updated_dates)
    return bundle
