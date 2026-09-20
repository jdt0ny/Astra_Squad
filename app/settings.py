"""
Impostazioni App
=================

Oggetti runtime condivisi per la piattaforma.
"""

from __future__ import annotations

from os import getenv

from agno.models.groq import Groq

# ── Fallback locale (Ollama) — zero costi, rate limit infinito ──────
_ollama_model = getenv("OLLAMA_MODEL", "qwen2.5-coder:7b")
_ollama_url = getenv("OLLAMA_URL", "http://localhost:11434")


def _groq_model():
    """Prova Groq; restituisce None se la chiave manca."""
    api_key = getenv("GROQ_API_KEY") or getenv("OPENAI_API_KEY")
    if not api_key:
        return None
    try:
        return Groq(id="llama-3.3-70b-versatile")
    except Exception:
        return None


def _ollama_model():
    """Prova Ollama locale; restituisce None se non raggiungibile."""
    try:
        from agno.models.ollama import Ollama

        return Ollama(id=_ollama_model, host=_ollama_url)
    except Exception:
        return None


def default_model():
    """Modello con fallback automatico: Groq → Ollama.

    Groq è prioritario (più veloce, migliore), Ollama è il piano B
    locale e gratuito. Se entrambi falliscono, usa Groq anyway
    (fallirà a runtime con un errore chiaro).
    """
    model = _groq_model()
    if model is not None:
        return model
    model = _ollama_model()
    if model is not None:
        return model
    # Ultima risorsa: Groq senza garanzia
    return Groq(id="llama-3.3-70b-versatile")
