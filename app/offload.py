"""
Scaricamento dei Risultati
===========================

Scarica i grandi risultati degli strumenti su un database invece che sulla finestra di contesto.

Uno strumento che restituisce un'intera pagina web, un intero file sorgente o un intero payload
di metriche costa altrettanto contesto ad ogni turno successivo della sessione. Lo scaricamento
scrive qualsiasi cosa oltre la soglia su un database e lascia un breve involucro
nella trascrizione — un'anteprima, la dimensione e un `result_id` — poi passa al
componente `search_result` e `read_result` per tornare sulle parti di cui ha bisogno.
"""

from __future__ import annotations

from agno.offload import ResultStore

# Platform agents only. The four reference components do long back-and-forth work
# over big tool payloads — source files, metrics, registry listings, web pages —
# and that is what this is for. A new agent does not get it by default; wire it
# only when an agent's tool results are measured to outgrow its context.
RESULT_TTL_SECONDS = 7 * 24 * 60 * 60

result_store = ResultStore(ttl_seconds=RESULT_TTL_SECONDS)
