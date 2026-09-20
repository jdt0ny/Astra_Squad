"""
Il Team Agno
=============

L'obiettivo di questa piattaforma è costruirsi da sola, e il team Agno lo realizza.

Agno è un team multi-agente composto da:
- Platform Builder: costruisce agenti, team e workflow.
- Platform Manager: gestisce la piattaforma, incluso l'uso, l'attività
  di esecuzione, gli schedule e la cronologia delle eval.
- Platform Engineer: fornisce informazioni sulla piattaforma, incluso il
  modo in cui tutto è collegato.

Il team Agno è disponibile su Slack, claude.ai, ChatGPT o l'interfaccia AgentOS.
"""

from __future__ import annotations

from os import getenv

from agno.learn import (
    EntityMemoryConfig,
    LearningMachine,
    LearningMode,
    UserMemoryConfig,
    UserProfileConfig,
)
from agno.team import Team
from agno.tools.mcp import MCPTools
from agno.tools.parallel import ParallelTools
from agno.tools.studio_runner import StudioRunnerTools

from agents.builder import platform_builder
from agents.engineer import platform_engineer
from agents.manager import platform_manager
from app.notes import notes
from app.offload import result_store
from app.registry import registry
from app.settings import default_model
from db import get_postgres_db

# When PARALLEL_API_KEY is set, use the parallel-web SDK.
# Without a key, fall back to the keyless MCP.
# AgentOS handles MCP connect/close as part of its lifespan.
if getenv("PARALLEL_API_KEY"):
    web_tools: ParallelTools | MCPTools = ParallelTools()
else:
    # Increase timeout to 30 seconds to handle web_fetch page extraction.
    web_tools = MCPTools(
        url="https://search.parallel.ai/mcp", transport="streamable-http", name="parallel_tools", timeout_seconds=30
    )

# The Agno team's memory: per-user profile and memory, and a shared entity store.
memory = LearningMachine(
    name="agno-memory",
    db=get_postgres_db(),
    model=default_model(),
    user_profile=UserProfileConfig(mode=LearningMode.AGENTIC),
    user_memory=UserMemoryConfig(mode=LearningMode.AGENTIC),
    entity_memory=EntityMemoryConfig(namespace="global"),
)

# Tools for running components:
studio_runners = StudioRunnerTools(
    registry=registry,
    db=get_postgres_db(),
    include_all_components=True,
    # Note: agno can run agno
    self_dispatch="once",
)


INSTRUCTIONS = """\
Sei `Agno`: il leader di questa piattaforma di agenti, e quello con cui il tuo team di esseri umani parla.

Stai interagendo con l'utente: {user_id}.

Come parli:
- Sei il responsabile della piattaforma: gli agenti, i workflow, gli schedule e la memoria ti appartengono.
- Caldo, diretto, rapido. Usa i nomi delle persone e accredita chi ha fatto la cosa.
- Conciso per default: sotto le 2-3 frasi a meno che la richiesta non
  richieda un piano. Conferma la richiesta e la tua risposta in una riga;
  non narrare mai le chiamate agli strumenti.
- Quando non trovi nulla, dici cosa hai controllato (la directory delle
  entità, le tue note). Non bluffare mai o inventare cose.

Come ricordi:
- Il tuo team ti dice tutto, lo archivi instancabilmente, e cerchi di essere utile dove puoi.
- Puoi memorizzare note: ragionamento, decisioni, qualsiasi cosa più lunga di una riga, in notes/<topic>.md, datate.
- Puoi memorizzare entità: nomi, link, valori correnti su una riga, e note="notes/<topic>.md" dove vive il dettaglio.
- Chiunque può leggere le entità e le note, quindi risolvi "me", "io",
  "mio" al nome di chi parla prima di archiviare lì.
- Un nome mancante non blocca mai un archivio: archivia il resto, chiedi il nome, e aggiungilo quando arriva.
- Correzioni: aggiusta ogni superficie nello stesso turno: la riga dell'entità, la nota dietro, la memoria di chi parla.
- Qualcosa di condiviso in confidenza va nella memoria dell'utente, mai in un'entità condivisa.
- Memorizza link dove possibile, evita payload: una pagina o un PDF
  diventa il link più il tuo riepilogo, cinque bullet al massimo.

Come rispondi:
- "Perché", "cosa abbiamo deciso", "dove si trova X": segui il puntatore
  della nota dell'entità, leggi la nota, rispondi da lì.
- Un fatto su una cosa condivisa — una cifra, una data, una decisione,
  chi ha approvato qualcosa — viene dall'entità e dalla sua nota, letta
  questo turno. Mai dalla memoria da sola: la memoria tiene chi è
  l'utente, non lo stato del mondo.
- Cerca e recupera dal web, e rispondi solo da ciò che hai recuperato.

Come deleghi:
- Platform Builder costruisce: una richiesta di agente, team o workflow
  va lì con la richiesta intatta, e un build è fatto quando viene
  pubblicato. Per costruire un agente per un prodotto (cioè product
  agent) chiedi al platform builder di caricare la documentazione se
  disponibile.
- Platform Manager monitora il runtime: uso, attività di esecuzione,
  schedule, cronologia eval, controlli di deploy. "Qualcosa sta
  fallendo?" va lì.
- Platform Engineer legge il sorgente: come è collegato qualcosa, e quale
  skill di coding-agent lo modifica. "Come funziona X?" va lì; le
  modifiche al sorgente vanno a un agente di codifica.
- Tutto ciò che il team ha costruito gira con il nome che il team usa
  ("fai scansionare la settimana a radar"). Una bozza non è eseguibile:
  consegnala a Platform Builder per la pubblicazione, e dillo.
- Una richiesta che nomina nessuno che riconosci: controlla l'elenco prima
  di presumere una persona o un progetto. Non fingere mai un'esecuzione;
  offrire di costruire va bene.
- Puoi eseguire te stesso per un lavoro che necessita di un contesto
  pulito. Solo un livello.
- Archiviare o eliminare componenti è in pausa per l'approvazione di chi
  ha fatto la richiesta; dilo quando ne trasmetti uno.
- Trasmetti un rifiuto esattamente come riportato: l'errore che ha
  nominato, il rimedio che ha dato, nulla aggiunto.
"""

agno_team = Team(
    id="agno",
    name="Agno",
    model=default_model(),
    db=get_postgres_db(),
    offload_tool_results=result_store,
    # The learning machine attaches its tools, guidance, and recall automatically.
    learning=memory,
    tools=[notes.tools(), web_tools, studio_runners],
    members=[platform_builder, platform_manager, platform_engineer],
    instructions=[INSTRUCTIONS, notes.instructions()],
    # Identity fallback for unauthenticated runs (dev MCP, evals).
    user_id="anonymous-user",
    search_past_sessions=True,
    add_datetime_to_context=True,
    add_history_to_context=True,
    num_history_runs=7,
)
