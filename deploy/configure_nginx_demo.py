"""Executar na VPS: adiciona só o vhost público, preservando arquivo e inode.

Backup e rollback se nginx -t/reload falhar. Não altera vhosts existentes.
"""
import argparse
import shutil
import subprocess
import re
from datetime import datetime, timezone
from pathlib import Path

DOMAIN = "analisejacare.pedromerli.com"
PATH = Path("/opt/evolync/nginx/runtime/evolync.conf")
START = "# BEGIN JACARE DEMO MANAGED"
END = "# END JACARE DEMO MANAGED"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["http", "https"])
    parser.add_argument("--private", action="store_true")
    args = parser.parse_args()
    global DOMAIN, START, END
    upstream = "jacare_demo"
    if args.private:
        DOMAIN = "jacare.pedromerli.com"
        START, END = "# BEGIN JACARE PRIVATE MANAGED", "# END JACARE PRIVATE MANAGED"
        upstream = "jacare_private"
    original = PATH.read_text()
    existing_names = [name for group in re.findall(r"server_name\s+([^;]+);", original) for name in group.split()]
    if START not in original and DOMAIN in existing_names:
        raise ValueError("Vhost já existe fora do bloco gerenciado; revisar antes de editar.")
    if START in original:
        begin, finish = original.index(START), original.index(END)+len(END)
        prefix, suffix = original[:begin], original[finish:]
    else:
        prefix, suffix = original.rstrip()+"\n\n", "\n"
    location = "location ^~ /.well-known/acme-challenge/ { root /var/www/certbot; }"
    http = f"server {{\n listen 80;\n listen [::]:80;\n server_name {DOMAIN};\n {location}\n location / {{ return 503; }}\n}}"
    if args.phase == "https":
        cert = Path("/etc/letsencrypt/live")/DOMAIN
        if not (cert/"fullchain.pem").exists() or not (cert/"privkey.pem").exists():
            raise ValueError("Certificado HTTPS ainda ausente")
        http = http.replace("return 503;", "return 301 https://$host$request_uri;")
        http += f"\nserver {{\n listen 443 ssl;\n listen [::]:443 ssl;\n server_name {DOMAIN};\n ssl_certificate {cert}/fullchain.pem;\n ssl_certificate_key {cert}/privkey.pem;\n ssl_protocols TLSv1.2 TLSv1.3;\n client_max_body_size 1m;\n location / {{\n proxy_pass http://{upstream}:8501;\n include /etc/nginx/conf.d/proxy_params.conf;\n }}\n}}"
    replacement = prefix+START+"\n"+http+"\n"+END+suffix
    tag = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = PATH.with_name(f"evolync.conf.backup-jacare-{args.phase}-{tag}")
    shutil.copy2(PATH, backup)
    # In-place: o arquivo está montado via bind e precisa manter seu inode.
    PATH.write_text(replacement)
    try:
        for command in (["docker","exec","evolync_nginx","nginx","-t"], ["docker","exec","evolync_nginx","nginx","-s","reload"]):
            result = subprocess.run(command, capture_output=True, text=True)
            if result.returncode:
                errors = "\n".join(line for line in result.stderr.splitlines() if "[emerg]" in line)
                raise RuntimeError("Nginx recusou atualização; rollback automático. " + errors)
    except Exception:
        PATH.write_text(original)
        subprocess.run(["docker","exec","evolync_nginx","nginx","-s","reload"], capture_output=True)
        raise
    print(f"Vhost {DOMAIN} atualizado ({args.phase}); backup preservado em {backup}.")


if __name__ == "__main__":
    main()
