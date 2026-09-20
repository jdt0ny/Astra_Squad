"""
Sessione del Database
=====================

Helper di connessione PostgreSQL. Usa:
- get_postgres_db() per l'archivio degli agenti basato su Postgres.
- create_knowledge() per la conoscenza degli agenti basata su PgVector.
"""

from __future__ import annotations

from functools import cache
from os import getenv

from agno.db.postgres import PostgresDb
from agno.knowledge import Knowledge
from agno.vectordb.pgvector import PgVector, SearchType

from db.url import db_url

DB_ID = "agentos-db"


@cache
def get_postgres_db(contents_table: str | None = None) -> PostgresDb:
    """Restituisce l'istanza condivisa di PostgresDb per l'AgentOS.

    Memorizzata in cache così che ogni agente/workflow/schedule riutilizzi lo stesso oggetto
    invece di costruire un nuovo PostgresDb ad ogni chiamata.

    Passa contents_table quando questo database viene usato come contents_db di una Knowledge base.
    Per la persistenza semplice degli agenti (sessioni, memoria), lascialo non impostato.
    """
    if contents_table is not None:
        return PostgresDb(id=f"{DB_ID}-{contents_table}", db_url=db_url, knowledge_table=contents_table)
    return PostgresDb(id=DB_ID, db_url=db_url)


def create_knowledge(name: str, table_name: str) -> Knowledge:
    """Crea una knowledge base PgVector con ricerca ibrida.

    Richiede OPENAI_API_KEY per gli embeddings. Senza di essa, restituisce un
    placeholder che permette alla piattaforma di avviarsi — le funzionalità di conoscenza
    si attivano una volta impostata la chiave.
    """
    if not getenv("OPENAI_API_KEY"):
        from agno.knowledge import Knowledge as _Placeholder
        # Return a minimal placeholder — knowledge features are inactive
        # but the platform boots and the squad runs on Groq.
        return _Placeholder(name=name, contents_db=get_postgres_db(contents_table=f"{table_name}_contents"))

    from agno.knowledge.embedder.openai import OpenAIEmbedder
    return Knowledge(
        name=name,
        vector_db=PgVector(
            db_url=db_url,
            table_name=table_name,
            search_type=SearchType.hybrid,
            embedder=OpenAIEmbedder(id="text-embedding-3-small"),
        ),
        contents_db=get_postgres_db(contents_table=f"{table_name}_contents"),
    )
