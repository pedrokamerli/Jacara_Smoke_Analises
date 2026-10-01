"""Pacote de implantação por allowlist: nunca inclui data, originais ou secrets."""
import hashlib
import json
import tarfile
from datetime import datetime, timezone
from pathlib import Path

from jacare_analytics.runtime_config import PUBLIC_ARTIFACTS, load_runtime_config, validate_public_manifest

ROOT = Path(__file__).resolve().parents[1]


def main():
    config = load_runtime_config(ROOT, {"JACARE_PUBLIC_MODE":"true"})
    manifest = json.loads(config.current_manifest_path.read_text(encoding="utf-8"))
    validate_public_manifest(manifest, config)
    fixed = ["Dockerfile", ".dockerignore", "requirements.txt", "pyproject.toml", "app/streamlit_app.py",
             ".streamlit/config.toml", "config/business_calendar.json", "demo/public/current_run.json"]
    fixed += ["demo/public/"+relative for relative in sorted(PUBLIC_ARTIFACTS)]
    fixed += [path.relative_to(ROOT).as_posix() for path in sorted((ROOT/"src/jacare_analytics").glob("*.py"))]
    tag = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output = ROOT/"data/private/deploy"/f"demo-{tag}.tar.gz"
    output.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(output, "x:gz") as archive:
        for relative in fixed:
            path = ROOT/relative
            if path.is_symlink() or not path.is_file():
                raise ValueError("Pacote com link ou arquivo ausente")
            archive.add(path, arcname=relative, recursive=False)
        archive.add(ROOT/"deploy/compose.demo.yaml", arcname="compose.yaml", recursive=False)
    with tarfile.open(output) as archive:
        members = archive.getmembers()
        if {m.name for m in members} != set(fixed)|{"compose.yaml"} or any(not m.isfile() for m in members):
            raise ValueError("Pacote fora da lista permitida")
    print(output)
    print("SHA256:", hashlib.sha256(output.read_bytes()).hexdigest())
    print("Somente código, configuração não secreta e quatro artefatos sintéticos.")


if __name__ == "__main__":
    main()
