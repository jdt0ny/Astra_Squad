"""
Esecuzione delle Evals
======================

python -m evals                         # esegue tutti i casi (UI concisa)
python -m evals --tag smoke             # esegue un sottoinsieme con tag
python -m evals --name <case>           # esegue un singolo caso
python -m evals --tag smoke --list      # mostra cosa seleziona un tag, senza spese
python -m evals --timeout 180           # timeout per caso per i casi senza impostazione (120s)
python -m evals --json-output out.json  # scrive i risultati in formato leggibile dalla macchina
python -m evals -v                      # trasmette l'esecuzione dell'agente con pannelli completi

L'eval runner di Agno esegue ogni caso e valuta la risposta con `AgentAsJudgeEval`
(quando `criteria` è impostato) e/o `ReliabilityEval` (quando `expected_tool_calls` è impostato).

Il codice di uscita 0 significa che tutti i casi selezionati sono passati, 1 significa che uno è fallito
(o la scrittura di `--json-output` lo è), e 2 significa che il selettore non ha trovato nulla — così un
`--tag` digitato male fa fallire un gate CI invece di verde su un'esecuzione vuota.

Entrambi registrano su Postgres tramite `eval_db`. Connetti il tuo AgentOS su os.agno.com per vedere la cronologia.
"""

from __future__ import annotations

# Hydrate os.environ from .env before any module that reads env at import time
# (db_url, model factories, etc.). Pre-existing shell vars take precedence.
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

import sys  # noqa: E402

from agno.eval import cli  # noqa: E402
from agno.os.utils import collect_mcp_tools_from_registry  # noqa: E402

from app.registry import registry  # noqa: E402
from evals.cases import CASES, eval_db  # noqa: E402

# Behind the guard so an import never costs money
if __name__ == "__main__":
    # AgentOS connects to the registry's MCP toolkits in its server lifecycle.
    # This standalone process does not have an equivalent, so hand them to the runner instead.
    # The runner connects them before the cases run and closes them afterwards.
    mcp_tools: list = []
    collect_mcp_tools_from_registry(registry, mcp_tools)
    sys.exit(cli(CASES, db=eval_db, mcp_tools=mcp_tools))
