"""Funções de minimização e pseudonimização para processamento local.

Chaves HMAC continuam sendo dados pseudonimizados, não dados anônimos. A chave
secreta deve ser mantida fora do repositório e das tabelas analíticas públicas.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets
import unicodedata
from pathlib import Path

KEY_ENV_VAR = "JACARE_ANALYTICS_HMAC_KEY"


def local_secret(private_dir: Path) -> str:
    """Usa segredo configurado ou cria uma chave local estável, sem registrá-la em logs."""
    configured = os.environ.get(KEY_ENV_VAR)
    if configured:
        _secret_key(configured)
        return configured
    private_dir.mkdir(parents=True, exist_ok=True)
    path = private_dir / "hmac.key"
    if not path.exists():
        with path.open("x", encoding="utf-8") as handle:
            handle.write(secrets.token_hex(32))
    secret = path.read_text(encoding="utf-8").strip()
    _secret_key(secret)
    return secret


def _secret_key(secret: str | bytes | None = None) -> bytes:
    value = secret if secret is not None else os.environ.get(KEY_ENV_VAR)
    if isinstance(value, str):
        value = value.encode("utf-8")
    if not value or len(value) < 32:
        raise ValueError(
            f"Defina {KEY_ENV_VAR} com um segredo aleatório de pelo menos 32 bytes; "
            "não o salve no repositório."
        )
    return value


def _pseudonym(namespace: str, normalized_identifier: str, secret: str | bytes | None) -> str:
    key = _secret_key(secret)
    message = f"jacare-analytics:v1:{namespace}:{normalized_identifier}".encode("utf-8")
    digest = hmac.new(key, message, hashlib.sha256).hexdigest()
    return f"{namespace}_{digest}"


def pseudonymize_phone(
    phone: str | int | None,
    *,
    source: str,
    secret: str | bytes | None = None,
) -> str | None:
    """Gera um HMAC estável de telefone sem retornar nem registrar o telefone.

    A normalização remove pontuação e espaços. Valores ausentes ou com menos de
    10 dígitos são descartados para não criar chaves frágeis ou ambíguas.
    A chave é separada por fonte para impedir junções presumidas entre sistemas.
    """
    if phone is None:
        return None
    raw_phone = str(int(phone)) if isinstance(phone, float) and phone.is_integer() else str(phone)
    digits = re.sub(r"\D", "", raw_phone)
    if digits.startswith("55") and len(digits) in {12, 13}:
        digits = digits[2:]
    if not 10 <= len(digits) <= 13:
        return None
    safe_source = re.sub(r"[^a-z0-9_-]", "_", source.casefold()).strip("_")
    if not safe_source:
        raise ValueError("Informe uma origem válida para separar as chaves por sistema.")
    return _pseudonym(f"phone_{safe_source}", digits, secret)


def pseudonymize_external_id(
    identifier: str | int | None,
    *,
    source: str,
    secret: str | bytes | None = None,
) -> str | None:
    """Pseudonimiza um ID de cliente de uma fonte, mantendo seu namespace local."""
    if identifier is None:
        return None
    normalized = unicodedata.normalize("NFKC", str(identifier)).strip().casefold()
    if not normalized:
        return None
    safe_source = re.sub(r"[^a-z0-9_-]", "_", source.casefold()).strip("_")
    if not safe_source:
        raise ValueError("Informe uma origem válida para separar as chaves por sistema.")
    return _pseudonym(f"id_{safe_source}", normalized, secret)
