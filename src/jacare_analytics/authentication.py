"""Autorização após OIDC validado pelo Streamlit; nunca aceita claims do browser."""
from __future__ import annotations

import math
import os
import time
from collections.abc import Mapping

GOOGLE_ISSUERS = {"https://accounts.google.com", "accounts.google.com"}


def authorized_import_admin(claims: Mapping, access: Mapping, now: float | None = None) -> bool:
    """Upload exige identidade verificada e política explícita no servidor."""
    if access.get("uploads_for_all_allowed") is True:
        return authorized_google_user(claims, access, now)
    admins = access.get("admin_emails", [])
    return (authorized_google_user(claims, access, now)
            and isinstance(admins, list) and bool(admins)
            and all(isinstance(value, str) and "@" in value for value in admins)
            and claims["email"].strip().lower() in {value.strip().lower() for value in admins})


def is_import_admin(public_mode: bool) -> bool:
    if public_mode:
        return False
    import streamlit as st
    try:
        return st.user.is_logged_in and authorized_import_admin(st.user.to_dict(), dict(st.secrets["access"]))
    except (KeyError, FileNotFoundError, ValueError):
        return False


def authorized_google_user(claims: Mapping, access: Mapping, now: float | None = None) -> bool:
    """Apenas identidade verificada, conta permitida e token/sessão ainda válidos.

    Não verifica assinatura: receber exclusivamente st.user após o fluxo OIDC,
    cuja validação criptográfica é responsabilidade de Streamlit/Authlib.
    """
    now = time.time() if now is None else now
    allowed = access.get("allowed_emails", [])
    maximum = access.get("max_session_seconds", 3600)
    if not isinstance(allowed, list) or not allowed or any(not isinstance(x, str) or "@" not in x for x in allowed):
        return False
    if type(maximum) is not int or not 300 <= maximum <= 3600:
        return False
    if claims.get("iss") not in GOOGLE_ISSUERS or claims.get("email_verified") is not True:
        return False
    if not isinstance(claims.get("sub"), str) or not claims["sub"]:
        return False
    email = claims.get("email")
    if not isinstance(email, str) or email.strip().lower() not in {x.strip().lower() for x in allowed}:
        return False
    issued, expiry = claims.get("iat"), claims.get("exp")
    if any(type(x) not in (int, float) or not math.isfinite(x) for x in (issued, expiry)):
        return False
    return issued <= now < min(expiry, issued + maximum) and expiry > issued


def enforce_private_access(public_mode: bool) -> None:
    """Deve rodar antes de ler manifesto, banco, métricas ou criar downloads."""
    if public_mode:
        return
    import streamlit as st

    mode = os.environ.get("JACARE_AUTH_MODE", "oidc").strip().lower()
    if mode == "local" and st.get_option("server.address") in {"127.0.0.1", "localhost", "::1"}:
        st.caption("Desenvolvimento local explícito, sem login. Não colocar este modo atrás de proxy público.")
        return
    if mode != "oidc":
        st.error("Acesso privado bloqueado: modo de autenticação inválido ou modo local exposto.")
        st.stop()
    try:
        auth = dict(st.secrets["auth"])
        access = dict(st.secrets["access"])
        required = ("redirect_uri", "cookie_secret", "client_id", "client_secret", "server_metadata_url")
        if any(not isinstance(auth.get(key), str) or not auth[key] or "SUBSTITUA" in auth[key] for key in required):
            raise ValueError("Configuração incompleta")
        if len(auth["cookie_secret"]) < 32 or auth["server_metadata_url"] != "https://accounts.google.com/.well-known/openid-configuration":
            raise ValueError("Configuração inválida")
        if not access.get("allowed_emails"):
            raise ValueError("Nenhuma conta autorizada")
    except (KeyError, ValueError, FileNotFoundError):
        st.error("Área privada bloqueada até configurar o login Google e as contas autorizadas. Consulte docs/10_login_e_vps.md.")
        st.stop()
    if not st.user.is_logged_in:
        st.title("Área privada - Jacaré Analytics")
        st.write("Entre com a conta Google previamente autorizada. Os dados do negócio não são carregados nesta tela.")
        if st.button("Entrar com Google"):
            st.login()
        st.stop()
    if not authorized_google_user(st.user.to_dict(), access):
        st.error("Conta não autorizada ou sessão expirada. Nenhum dado do negócio foi carregado.")
        if st.button("Sair / entrar novamente"):
            st.logout()
        st.stop()
    if st.sidebar.button("Sair da área privada"):
        st.logout()
        st.stop()
