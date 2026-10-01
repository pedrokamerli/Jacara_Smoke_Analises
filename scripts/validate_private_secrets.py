"""Valida configuração privada; reparo mecânico opcional de aspa ausente."""
import argparse
import shutil
import tomllib
from pathlib import Path
from datetime import datetime, timezone
import re

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repair-missing-quote", action="store_true")
    args = parser.parse_args()
    path = ROOT/".streamlit/secrets.toml"
    content = path.read_text(encoding="utf-8")
    if args.repair_missing_quote:
        # Apenas linhas de email dentro de [access], sem tocar em [auth].
        before, delimiter, access = content.partition("[access]")
        if not delimiter:
            raise ValueError("Seção de acesso ausente")
        repaired = re.sub(r'(?m)^(\s*"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,})\s*$', r'\1"', access)
        candidate = before+delimiter+repaired
        tomllib.loads(candidate)
        if candidate != content:
            backup = ROOT/"data/private/config_backups"/(datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")+".toml")
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, backup)
            # Correção mecânica de formato, sem inserir contas ou alterar credenciais.
            path.write_text(candidate, encoding="utf-8")
            content = candidate
            print("As aspas foram corrigidas; original preservado privadamente.")
    config = tomllib.loads(content)
    emails = config.get("access", {}).get("allowed_emails")
    if not isinstance(emails, list) or not emails or any(not isinstance(x,str) or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+",x) or x.endswith("@example.com") for x in emails):
        raise ValueError("Lista de contas inválida")
    if config["auth"]["redirect_uri"] != "https://jacare.pedromerli.com/oauth2callback":
        raise ValueError("Callback inválido")
    print(f"Configuração válida: {len(emails)} conta(s) autorizada(s). Nenhuma credencial exibida.")


if __name__ == "__main__":
    main()
