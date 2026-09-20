"""
URL del Database
================
"""

from __future__ import annotations

from os import getenv
from urllib.parse import quote


def build_db_url() -> str:
    """Costruisce l'URL del database dalle variabili d'ambiente.

    In produzione, aggiunge i parametri del pool di connessione per SQLAlchemy.
    Sovrascrivere tramite env: DB_POOL_SIZE, DB_MAX_OVERFLOW, DB_POOL_TIMEOUT, DB_POOL_RECYCLE.
    """
    driver = getenv("DB_DRIVER", "postgresql+psycopg")
    user = getenv("DB_USER", "ai")
    password = quote(getenv("DB_PASS", "ai"), safe="")
    host = getenv("DB_HOST", "localhost")
    port = getenv("DB_PORT", "5432")
    database = getenv("DB_DATABASE", "ai")

    base = f"{driver}://{user}:{password}@{host}:{port}/{database}"

    # Connection pooling — only in production (prd) where multiple requests
    # hit the DB concurrently. Dev stays at defaults for simplicity.
    if getenv("RUNTIME_ENV", "prd") != "dev":
        pool_size = getenv("DB_POOL_SIZE", "10")
        max_overflow = getenv("DB_MAX_OVERFLOW", "20")
        pool_timeout = getenv("DB_POOL_TIMEOUT", "30")
        pool_recycle = getenv("DB_POOL_RECYCLE", "1800")
        base += (
            f"?pool_size={pool_size}"
            f"&max_overflow={max_overflow}"
            f"&pool_timeout={pool_timeout}"
            f"&pool_recycle={pool_recycle}"
            f"&pool_pre_ping=true"
        )

    return base


db_url = build_db_url()
