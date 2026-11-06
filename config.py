"""Configuração da aplicação (lida de variáveis de ambiente)."""
import os
from datetime import timedelta


def _secret_key() -> str:
    key = os.environ.get("SECRET_KEY", "")
    if len(key) < 32:
        raise RuntimeError(
            "Defina a variável de ambiente SECRET_KEY com pelo menos 32 caracteres. "
            'Para gerar: python -c "import secrets; print(secrets.token_hex(32))"'
        )
    return key


class Config:
    SECRET_KEY = _secret_key()

    # Caminho do JSON da conta de serviço do Firebase. Deixe vazio para usar as credenciais
    # padrão do ambiente (ex.: conta de serviço anexada ao Cloud Run).
    FIREBASE_CREDENTIALS = os.environ.get("FIREBASE_CREDENTIALS", "")

    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    # Cookie só trafega por HTTPS. Para testar localmente em http, defina SESSION_COOKIE_SECURE=0.
    SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "1") == "1"
    # 1 quando publicado atrás de um proxy reverso (Cloud Run, Render...)
    TRUST_PROXY = os.environ.get("TRUST_PROXY", "0") == "1"
    # Cache em memória das coleções do Firestore (reduz leituras). 0 = sem expiração (1 instância).
    # Com mais de uma instância/processo, use um valor como 300 (segundos).
    CACHE_TTL_SECONDS = float(os.environ.get("CACHE_TTL_SECONDS", "0"))
    MAX_CONTENT_LENGTH = 1024 * 1024  # 1 MB por requisição
