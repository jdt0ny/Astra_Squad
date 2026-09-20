"""
Hook delle Eval
===============

La meccanica di setup/teardown dietro `evals/cases.py`: snapshot pre-caso e
sweep post-caso dei componenti Studio, schedule, righe di apprendimento e note.
La cattura e la creazione/modifica/pubblicazione non sono bloccate, quindi le righe
di un caso atterrano veramente negli archivi condivisi — questi hook rimuovono ciò che
il caso ha creato, e rifiutano invece di indovinare quando uno snapshot sembra incompleto.

I casi usano le coppie pronte:

- `**BUILDER_HOOKS` — qualsiasi caso il cui componente può raggiungere gli strumenti
  di creazione/modifica/pubblicazione senza blocco del builder: ogni caso `platform-builder`,
  e qualsiasi caso `agno` a una delega dalla creazione. Pulisce componenti, schedule e apprendimenti.
- `**LEARNING_HOOKS` — ogni altro caso che esplora un componente con archivio di apprendimento
  (`agno`, `platform-manager`, `platform-engineer`). Pulisce entità, memorie,
  profili e note.

La coppia del builder è un superinsieme rigoroso, quindi promuovere un caso borderline è sicuro.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

from agno.eval import CaseResult
from agno.run.base import RunStatus
from agno.scheduler.manager import ScheduleManager

from app.notes import notes
from db import get_postgres_db

# Eval DB instance (where results are stored)
eval_db = get_postgres_db()

_COMMIT_GRACE_SECONDS = 10


async def _let_inflight_writes_land(result: CaseResult) -> None:
    """Attende che una scrittura in corso sia completata prima dello sweep, quando l'esecuzione è stata interrotta.

    Il costo è una pausa all'abort — Ctrl-C durante un caso del builder richiede questo tempo per uscire —
    e compensa la perdita che la pausa previene: un componente pubblicato che nessuno ha pulito, o
    uno schedule creato dal caso che poi scatta quotidianamente."""
    if result.response is not None and result.response.status == RunStatus.completed:
        return
    await asyncio.sleep(_COMMIT_GRACE_SECONDS)


def snapshot_component_ids() -> set[str]:
    """Hook di `setup` per i casi Studio-builder: gli id dei componenti Studio presenti prima
    dell'esecuzione del caso. Il runner passa l'insieme restituito al teardown come contesto.
    Le lapidi sono incluse così che un componente archiviato preesistente non venga mai letto
    come nuovo nella differenza (lo sweep lo eliminerebbe definitivamente)."""
    components, _ = eval_db.list_components(limit=1000, include_deleted=True)
    return {component["component_id"] for component in components}


def delete_new_components(pre_run_ids: set[str]) -> None:
    """Elimina definitivamente solo i componenti che non esistevano prima dell'esecuzione del caso —
    i componenti propri dell'utente non vengono mai toccati, qualunque sia il nome che l'esecuzione
    eval ha dato alle sue creazioni. Usato anche autonomamente dalla skill improve-agent per
    delimitare i cicli di sonda contro gli agenti Studio-builder."""
    # include_deleted: a component the case created and then archived would
    # otherwise vanish from the listing and leak its tombstone. Workflows and
    # teams go before agents so dependent tracking never refuses a member's
    # delete mid-sweep.
    components, _ = eval_db.list_components(limit=1000, include_deleted=True)
    new = [component for component in components if component["component_id"] not in pre_run_ids]
    order = {"workflow": 0, "team": 1, "agent": 2}
    new.sort(key=lambda component: order.get(str(component.get("component_type", "")), 3))
    for component in new:
        eval_db.delete_component(component["component_id"], hard_delete=True)


async def cleanup_new_components(pre_run_ids: set[str], result: CaseResult) -> None:
    """Hook di `teardown` per i casi la cui esecuzione può creare componenti Studio (creazione/
    modifica/pubblicazione non sono bloccate, quindi i componenti atterrano veramente nel DB).
    Il runner lo invoca su pass, fail, error e timeout allo stesso modo, con lo snapshot di
    `setup` come contesto."""
    await _let_inflight_writes_land(result)
    await asyncio.to_thread(delete_new_components, pre_run_ids)


def snapshot_learning_state() -> dict[str, set[str]]:
    """Hook di `setup` per i casi che esplorano un componente con archivi di apprendimento (agno,
    platform-builder, platform-manager, platform-engineer): gli id di apprendimento (entità,
    profili, memorie) e i percorsi delle note presenti prima dell'esecuzione del caso, così il teardown
    può eliminare solo ciò che il caso ha creato.

    `taken_at` è il limite su cui si basa il rifiuto del teardown: secondi epoch, lo stesso
    orologio e la stessa troncatura con cui `created_at` della tabella degli apprendimenti viene scritto
    (`int(time.time())`, nel processo che esegue l'agente — il processore eval stesso, in
    entrambi i percorsi autorizzati). Viaggia in un insieme a un elemento così l'intero snapshot resta un
    dict di insiemi di stringhe: la skill improve-agent lo passa attraverso JSON con
    `sorted()` in uscita e `set()` al ritorno."""
    # The cutoff is read before the rows, never after — a row written between the two
    # would otherwise look older than the snapshot and trip the refusal for nothing.
    taken_at = int(time.time())
    return {
        "taken_at": {str(taken_at)},
        "learning_ids": {str(row["learning_id"]) for row in eval_db.get_learnings()},
        "note_paths": {meta.path for meta in notes.list()},
    }


# Second line of defence behind the predating-row refusal in delete_new_learning_state:
# one case writes a handful of learning rows, so far more than this is worth a human look
# even when every new row does postdate the snapshot — a capture loop that ran away, or a
# second writer on the platform during the case window.
_MAX_SWEPT_LEARNINGS = 25


def _snapshot_cutoff(pre_run: dict[str, set[str]]) -> int:
    """Il secondo epoch `taken_at` da uno snapshot di apprendimento.

    Uno snapshot senza esattamente uno è costruito a mano o di una forma precedente, e non può
    trasportare il rifiuto qui sotto. Comunicalo invece di fare sweep con la protezione silenziosamente disattivata."""
    stamps = pre_run.get("taken_at") or set()
    if len(stamps) != 1:
        raise RuntimeError(
            "refusing to sweep learning rows: this snapshot carries no single 'taken_at' cutoff, "
            "so a row cannot be told apart from one that predates the case. Re-take it with "
            "snapshot_learning_state()."
        )
    return int(next(iter(stamps)))


def delete_new_learning_state(pre_run: dict[str, set[str]], max_swept: int | None = None) -> None:
    """Elimina definitivamente gli apprendimenti (entità, profili, memorie) e le note che non esistevano
    prima dell'esecuzione del caso. Usato anche autonomamente dalla skill improve-agent per
    delimitare i cicli di sonda contro gli agenti con archivio di apprendimento (senza limite lì —
    una campagna di sonde crea legittimamente molte righe)."""
    # Read before anything is deleted, so a snapshot of the wrong shape refuses first.
    taken_at = _snapshot_cutoff(pre_run)
    # Notes first: their snapshot cannot be silently empty (notes.list() raises on DB
    # failure, failing the setup), so they are safe to sweep even when the learnings
    # guard below refuses.
    for meta in notes.list():
        if meta.path not in pre_run["note_paths"]:
            notes.delete(meta.path)
    new = [row for row in eval_db.get_learnings() if str(row["learning_id"]) not in pre_run["learning_ids"]]
    # The guard that matters, and the reason it is structural rather than a count: this is
    # the only path in the repo that hard-deletes user data, and get_learnings swallows DB
    # errors into an empty list, so one transient failure during `setup` makes every
    # pre-existing row read as new. A row created before the snapshot was taken cannot be a
    # row this case created, so one appearing here is proof the snapshot missed rows — and
    # that proof shows up at any platform size, which a count never does: at a dozen rows —
    # a platform a few conversations old — `12 > 25` is False, no cap fires, and every user
    # profile, memory, and shared entity goes. A NULL created_at counts as predating too:
    # unattributable is precisely what the refusal is for.
    predating = sorted(str(row["learning_id"]) for row in new if int(row.get("created_at") or 0) < taken_at)
    if predating:
        raise RuntimeError(
            f"refusing to sweep learning rows: {len(predating)}/{len(new)} rows missing from the "
            f"pre-case snapshot were created before it was taken (e.g. {predating[0]}) — the "
            "snapshot is incomplete, so none of them are safely attributable to the case. Inspect "
            "them and delete by hand: eval_db.delete_learning(<id>)."
        )
    if max_swept is not None and len(new) > max_swept:
        raise RuntimeError(
            f"refusing to sweep {len(new)} learning rows (cap {max_swept}): that is far more than a "
            "case writes, so these rows are not safely attributable to it. "
            "Inspect them and delete by hand: eval_db.delete_learning(<id>)."
        )
    for row in new:
        eval_db.delete_learning(str(row["learning_id"]))


async def cleanup_new_learning_state(pre_run: dict[str, set[str]], result: CaseResult) -> None:
    """Hook di `teardown` per i casi la cui esecuzione può scrivere negli archivi di apprendimento
    (la cattura non è bloccata, quindi entità, memorie e note atterrano veramente nel DB).
    Il runner lo invoca su pass, fail, error e timeout allo stesso modo, con lo snapshot di
    `setup` come contesto."""
    await _let_inflight_writes_land(result)
    await asyncio.to_thread(delete_new_learning_state, pre_run, _MAX_SWEPT_LEARNINGS)


def snapshot_schedule_ids() -> set[str]:
    """Gli id degli schedule presenti prima dell'esecuzione di un caso builder — il builder può creare
    schedule, e uno schedule creato dal caso lasciato indietro scatterebbe quotidianamente."""
    return {schedule.id for schedule in ScheduleManager(eval_db).list(limit=1000)}


# Registered by app/schedules.py on every boot. Spared by name because sweeping one
# costs real state: deployment-check stops running until the next boot, and run-evals
# returns disabled, silently reverting whoever enabled it. On a booted DB the spare is
# belt-and-braces (their ids pre-exist, and the boot registration's if_exists="update"
# refreshes the unowned rows in place rather than minting new ones); the guard in
# delete_new_schedules below covers the one case where name and id evidence disagree.
_CODE_REGISTERED_SCHEDULES = frozenset({"deployment-check", "run-evals"})

# A builder case creates a schedule or two. Far more looks like the same failure the
# learnings cap guards: get_schedules swallows DB errors into an empty list, so a
# transient failure during `setup` makes every existing schedule read as new.
_MAX_SWEPT_SCHEDULES = 5


def delete_new_schedules(pre_run_ids: set[str]) -> None:
    """Elimina definitivamente gli schedule che non esistevano prima dell'esecuzione del caso,
    risparmiando i due del template."""
    manager = ScheduleManager(eval_db)
    schedules = manager.list(limit=1000)
    # A reserved-named schedule the snapshot doesn't know is ambiguous: either the
    # snapshot silently failed (get_schedules swallows DB errors into an empty list)
    # and this is the real one, or the DB never booted and a case minted an impostor
    # that would outlive the sweep and stay enabled once a boot absorbs the name.
    # Neither should be resolved silently — refuse and let a human look.
    if not pre_run_ids and any(schedule.name in _CODE_REGISTERED_SCHEDULES for schedule in schedules):
        raise RuntimeError(
            "refusing to sweep schedules: the pre-case snapshot is empty but code-registered "
            "schedule names exist, so the real deployment-check/run-evals cannot be told apart "
            "from case-created rows. Inspect and delete by hand: ScheduleManager(eval_db).delete(<id>)."
        )
    new = [
        schedule
        for schedule in schedules
        if schedule.id not in pre_run_ids and schedule.name not in _CODE_REGISTERED_SCHEDULES
    ]
    if len(new) > _MAX_SWEPT_SCHEDULES:
        raise RuntimeError(
            f"refusing to sweep {len(new)} schedules (cap {_MAX_SWEPT_SCHEDULES}): the pre-case "
            "snapshot looks incomplete, so these are not safely attributable to the case. "
            "Inspect them and delete by hand: ScheduleManager(eval_db).delete(<id>)."
        )
    for schedule in new:
        manager.delete(schedule.id)


def snapshot_builder_state() -> dict[str, Any]:
    """Hook di `setup` per i casi Studio-builder: gli id dei componenti Studio, gli id degli schedule,
    e lo stato di apprendimento/note — il builder trasporta gli archivi condivisi di profilo/memoria
    per utente, così un'esecuzione può scrivere apprendimenti oltre che componenti e schedule."""
    return {
        "component_ids": snapshot_component_ids(),
        "schedule_ids": snapshot_schedule_ids(),
        "learning_state": snapshot_learning_state(),
    }


def delete_new_builder_state(pre_run: dict[str, Any]) -> None:
    """Elimina definitivamente componenti, schedule e righe di apprendimento/note che non esistevano
    prima dell'esecuzione del caso."""
    # Any sweep can refuse (see the caps) or hit a transient DB error; run each
    # regardless of how the others went, so one failure never strands another's rows.
    try:
        delete_new_components(pre_run["component_ids"])
    finally:
        try:
            delete_new_schedules(pre_run["schedule_ids"])
        finally:
            delete_new_learning_state(pre_run["learning_state"], _MAX_SWEPT_LEARNINGS)


async def cleanup_new_builder_state(pre_run: dict[str, Any], result: CaseResult) -> None:
    """Hook di `teardown` per i casi builder: pulisce i nuovi componenti, schedule e righe
    di apprendimento allo stesso modo. Il runner lo invoca su pass, fail, error e timeout allo stesso modo."""
    await _let_inflight_writes_land(result)
    await asyncio.to_thread(delete_new_builder_state, pre_run)


BUILDER_HOOKS: dict[str, Any] = {"setup": snapshot_builder_state, "teardown": cleanup_new_builder_state}
LEARNING_HOOKS: dict[str, Any] = {"setup": snapshot_learning_state, "teardown": cleanup_new_learning_state}
