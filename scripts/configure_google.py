"""Importa credenciais Google para arquivo privado, sem imprimir seus valores."""
import argparse
import json
import secrets
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--credentials", type=Path, required=True)
    args = parser.parse_args()
    config = json.loads(args.credentials.read_text(encoding="utf-8"))
    client = config.get("web", {})
    callbacks = client.get("redirect_uris", [])
    callback = "https://jacare.pedromerli.com/oauth2callback"
    if callback not in callbacks:
        raise ValueError("Callback de produção não cadastrado no cliente Web. Corrija no Google antes de continuar.")
    if not client.get("client_id") or not client.get("client_secret"):
        raise ValueError("Credenciais Web incompletas.")
    destination = ROOT / ".streamlit/secrets.toml"
    if destination.exists():
        raise ValueError("Arquivo privado existente preservado. Não sobrescrever credenciais automaticamente.")
    # json.dumps serializa strings compatíveis com TOML sem interpolar segredo em shell.
    quote = lambda value: json.dumps(value, ensure_ascii=True)
    content = "[auth]\n" + "\n".join(f"{key} = {quote(value)}" for key, value in {
        "redirect_uri":callback, "cookie_secret":secrets.token_hex(32),
        "client_id":client["client_id"], "client_secret":client["client_secret"],
        "server_metadata_url":"https://accounts.google.com/.well-known/openid-configuration",
    }.items()) + "\n\n[access]\nallowed_emails = []\nmax_session_seconds = 3600\n"
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("x", encoding="utf-8") as handle:
        handle.write(content)
    print("Credenciais importadas privadamente. Callback validado. Lista de contas vazia: acesso real permanece bloqueado.")


if __name__ == "__main__":
    main()
