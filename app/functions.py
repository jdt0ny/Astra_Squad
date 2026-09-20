"""Funzioni Workflow.

Costrutti deterministici per i workflow costruiti con Studio, registrati nello
slot `functions` del registro Studio (app/registry.py). Ogni funzione è un
esecutore di step: il runtime la chiama come `func(step_input)` con un
`StepInput`, e restituisce una stringa (il contenuto dello step) o un `StepOutput`.
"""

from __future__ import annotations

import csv
import io
import json
import re

from agno.media import File
from agno.workflow import StepInput, StepOutput
from pydantic import BaseModel

_URL_PATTERN = re.compile(r"https?://[^\s<>\"')\]]+")
_TABLE_ROW_CAP = 50
_MIN_CSV_ROWS = 2
_ERROR_PREFIX = "Error: "

_JsonValue = dict | list | str | int | float | bool | None


def _error(message: str) -> str:
    """Restituisce un errore di step su cui un workflow può fare branching invece di terminare."""
    return f"{_ERROR_PREFIX}{message}"


def _step_text(step_input: StepInput) -> str:
    """Restituisce il testo su cui opera uno step funzione: output dello step precedente o input del workflow."""
    content = step_input.previous_step_content
    if content is None:
        return step_input.get_input_as_string() or ""
    if isinstance(content, BaseModel):
        return content.model_dump_json(indent=2, exclude_none=True)
    if isinstance(content, (dict, list)):
        return json.dumps(content, indent=2, default=str, ensure_ascii=False)
    return str(content)


def _json_payload(text: str) -> dict | list | None:
    """Decodifica l'oggetto o array JSON più grande nel testo; `None` quando nessuno è valido.

    Il più grande, non il primo: anche le citazioni `[1]` e le checkbox `[ ]`
    di un agente raccoglitore vengono decodificate.
    """
    decoder = json.JSONDecoder()
    best_span, best_value, skip_until = 0, None, 0
    for match in re.finditer(r"[\[{]", text):
        start = match.start()
        if start < skip_until:  # inside a value already decoded
            continue
        try:
            value, end = decoder.raw_decode(text, start)
        except json.JSONDecodeError:
            continue
        if end - start > best_span:
            best_span, best_value = end - start, value
        skip_until = end
    return best_value


def _cell(value: _JsonValue) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def _table_cell(cell: str) -> str:
    return cell.strip().replace("|", "\\|").replace("\r\n", "\n").replace("\n", "<br>")


def extract_json(step_input: StepInput) -> str:
    """Restituisce l'oggetto o array JSON più grande nell'output dello step precedente.

    Restituisce `Error: ...` quando lo step precedente non ha prodotto JSON parsabile —
    inserire questo step tra un agente raccoglitore e qualsiasi step che necessiti di
    input strutturati. Un `Error: ` a monte viene passato invariato.
    """
    text = _step_text(step_input)
    if text.startswith(_ERROR_PREFIX):
        return text
    value = _json_payload(text)
    if value is None:
        return _error("no valid JSON object or array in the previous step's output")
    return json.dumps(value, indent=2, ensure_ascii=False)


def extract_urls(step_input: StepInput) -> str:
    """Restituisce le URL trovate nell'output dello step precedente, una per riga.

    Deduplicate in ordine. Restituisce `Error: ...` quando non contiene URL.
    Un `Error: ` a monte viene passato invariato.
    """
    text = _step_text(step_input)
    if text.startswith(_ERROR_PREFIX):
        return text
    chars = ".,;:!?`*"
    urls = dict.fromkeys(
        url.rstrip(chars) for url in _URL_PATTERN.findall(text)
    )
    if not urls:
        return _error("no URLs in the previous step's output")
    return "\n".join(urls)


def json_to_csv(step_input: StepInput) -> StepOutput:
    """Converte un array JSON di oggetti in un file artifact `data.csv` scaricabile.

    Le colonne sono l'unione delle chiavi degli oggetti in ordine di prima comparsa;
    i valori annidati vengono codificati JSON nella loro cella. Il CSV è anche il
    contenuto dello step, quindi uno step successivo — csv_to_markdown_table, per
    esempio — riceve i dati piuttosto che un riassunto. Restituisce `Error: ...`
    quando lo step precedente non contiene un array JSON di oggetti; un `Error: `
    a monte viene passato invariato. Posizionarlo al livello superiore del workflow:
    il file viene scartato quando questo step viene eseguito all'interno di una
    condizione, un loop o uno step parallelo, anche se il contenuto continua a fluire.
    """
    text = _step_text(step_input)
    if text.startswith(_ERROR_PREFIX):
        return StepOutput(content=text)
    value = _json_payload(text)
    if isinstance(value, dict):
        # Tolerate a single-array wrapper like {"rows": [...]}.
        arrays = [item for item in value.values() if isinstance(item, list)]
        if len(arrays) == 1:
            value = arrays[0]
    if (
        value is None
        or not isinstance(value, list)
        or not value
        or not all(isinstance(r, dict) for r in value)
    ):
        return StepOutput(
            content=_error("expected a JSON array of objects in the previous step's output"),
        )
    header: list[str] = []
    for row in value:
        for key in row:
            if key not in header:
                header.append(key)
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=header, extrasaction="ignore")
    writer.writeheader()
    for row in value:
        writer.writerow({key: _cell(row.get(key)) for key in header})
    data = buffer.getvalue()
    return StepOutput(
        content=data,
        files=[
            File(
                content=data.encode(),
                mime_type="text/csv",
                filename="data.csv",
            ),
        ],
    )


def csv_to_markdown_table(step_input: StepInput) -> str:
    """Renderizza il testo CSV dall'output dello step precedente come tabella markdown.

    Limitato a 50 righe di dati. Si abbina con json_to_csv. Restituisce `Error: ...`
    quando l'input non è CSV con una riga di intestazione e almeno una riga di dati,
    e passa invariato un `Error: ` a monte.
    """
    text = _step_text(step_input)
    if text.startswith(_ERROR_PREFIX):
        return text  # a failure upstream stays one failure, not two
    rows = [row for row in csv.reader(io.StringIO(text)) if row]
    if len(rows) < _MIN_CSV_ROWS:
        return _error(
            "expected CSV with a header row and at least one data row",
        )

    def line(cells: list[str]) -> str:
        return "| " + " | ".join(_table_cell(cell) for cell in cells) + " |"

    header, data = rows[0], rows[1:]
    lines = [line(header), "| " + " | ".join("---" for _ in header) + " |"]
    lines += [line(row) for row in data[:_TABLE_ROW_CAP]]
    if len(data) > _TABLE_ROW_CAP:
        lines.append(f"… {len(data) - _TABLE_ROW_CAP} more rows")
    return "\n".join(lines)


def content_to_file(step_input: StepInput) -> StepOutput:
    """Allega l'output dello step precedente come file artifact `output.md` scaricabile.

    Il contenuto continua anche come output dello step, quindi funziona come
    step finale di "pubblicazione del risultato" senza interrompere la catena.
    Restituisce `Error: ...` quando lo step precedente non ha prodotto contenuto;
    un `Error: ` a monte viene passato invariato, senza file. Posizionarlo al
    livello superiore del workflow: il file viene scartato quando questo step viene
    eseguito all'interno di una condizione, un loop o uno step parallelo, anche se
    il contenuto continua a fluire.
    """
    text = _step_text(step_input)
    if text.startswith(_ERROR_PREFIX):
        return StepOutput(content=text)
    if not text.strip():
        return StepOutput(content=_error("previous step produced no content to save"))
    return StepOutput(
        content=text,
        files=[
            File(
                content=text.encode(),
                mime_type="text/markdown",
                filename="output.md",
            ),
        ],
    )
