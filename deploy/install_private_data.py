"""Instala snapshot minimizado sob diretório privado; nunca imprime dados."""
import hashlib
import json
import os
import sys
import tarfile
from pathlib import Path, PurePosixPath

base = Path("/opt/portfolio/jacare-analytics/private")
archive = Path(sys.argv[1]).resolve()
if archive.parent != base or not archive.is_file() or archive.is_symlink():
    raise ValueError("Arquivo de instalação fora do diretório privado")
if hashlib.sha256(archive.read_bytes()).hexdigest() != sys.argv[2]:
    raise ValueError("Checksum de transferência inválido")
tag = archive.name.removesuffix(".tar.gz")
destination = base / "datasets" / tag
destination.mkdir(parents=True, exist_ok=False, mode=0o700)
with tarfile.open(archive) as package:
    members = package.getmembers()
    if len(members) != 8 or len({m.name for m in members}) != 8:
        raise ValueError("Quantidade de artefatos inválida")
    for member in members:
        path = PurePosixPath(member.name)
        if not member.isfile() or path.is_absolute() or ".." in path.parts or "\\" in member.name:
            raise ValueError("Membro inseguro")
        target = destination / member.name
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        stream = package.extractfile(member)
        with target.open("xb") as output:
            output.write(stream.read())
hashes = json.loads((destination / "integrity.json").read_text())
actual = {p.relative_to(destination).as_posix() for p in destination.rglob("*") if p.is_file()}
if actual != set(hashes) | {"integrity.json"}:
    raise ValueError("Inventário divergente")
for name, expected in hashes.items():
    if hashlib.sha256((destination / name).read_bytes()).hexdigest() != expected:
        raise ValueError("Artefato corrompido")
manifest = json.loads((destination / "data/current_run.json").read_text())
if manifest.get("dataset_kind") != "real_confidential" or manifest["quality"]["all_passed"] is not True:
    raise ValueError("Snapshot não aprovado")
for path in [destination, *destination.rglob("*")]:
    os.chown(path, 10001, 10001)
    path.chmod(0o700 if path.is_dir() else 0o400)
link = base / "data"
if link.exists() and not link.is_symlink():
    raise ValueError("Não substituir diretório preexistente")
candidate = base / ("data-" + tag)
candidate.symlink_to(destination / "data", target_is_directory=True)
os.replace(candidate, link)
archive.chmod(0o400)
print("Snapshot instalado: integridade conferida, permissões restritas, sem dados na imagem.")
