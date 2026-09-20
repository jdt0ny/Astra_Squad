"""
Note Condivise
==============

Un quaderno condiviso per i componenti della piattaforma
"""

from __future__ import annotations

from agno.fs import FileSystem
from agno.tools import Toolkit

from db import get_postgres_db

NOTES_NAMESPACE = "shared-notes"

notes = FileSystem(get_postgres_db(), namespace=NOTES_NAMESPACE)

SHARED_NOTES_INSTRUCTIONS = """\
Il quaderno condiviso è il modo in cui questa piattaforma ricorda le cose tra \
persone e componenti. Leggilo prima di rispondere a una domanda su cosa ha \
deciso il team, e archivia ciò che impari così il prossimo lettore non dovrà \
rifare il tuo lavoro. Chiunque sulla piattaforma può leggerlo, quindi archivia \
la scoperta e il ragionamento che ci sta dietro — un link e un riassunto \
distillato, mai un payload incollato. Raggruppa le note correlate in una \
directory e assegna a ciascuna un percorso datato o per soggetto; tieni i tuoi \
file di lavoro (liste visti, checkpoint) in una directory intitolata come te, \
un record per riga, e passa quella directory a check_lines e list_files così \
le note di un altro componente non rispondono al posto delle tue. Le note vengono \
sempre aggiunte, mai sostituite: append_file crea una nota o vi aggiunge qualcosa.\
"""


def get_shared_notes_tools() -> list[Toolkit]:
    """Il quaderno condiviso per i componenti costruiti: leggi, aggiungi, elenca, cerca, controlla.

    Nessuna scrittura, sostituzione, spostamento o eliminazione: queste operazioni
    ritirano il lavoro di un collega e restano ad Agno, che possiede il toolkit completo.
    """
    return [
        notes.tools(
            name="shared_notes",
            include_tools=["read_file", "append_file", "list_files", "search_content", "check_lines"],
            instructions=SHARED_NOTES_INSTRUCTIONS,
            # Built agents have no other channel for usage guidance.
            add_instructions=True,
        )
    ]
