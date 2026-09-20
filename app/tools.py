"""
Strumenti della Piattaforma
============================
"""

from __future__ import annotations

from os import getenv

from agno.tools.file import FileGenerationTools
from agno.tools.knowledge import KnowledgeManagementTools
from agno.tools.mcp import MCPTools
from agno.tools.openai import OpenAITools
from agno.tools.parallel import ParallelTools
from agno.tools.slack import SlackTools

from app.knowledge import product_knowledge

AGNO_DOCS_MCP_URL = "https://docs.agno.com/mcp"


def get_agno_docs_tools() -> list[MCPTools]:
    return [MCPTools(transport="streamable-http", url=AGNO_DOCS_MCP_URL, name="agno_docs")]


def get_parallel_tools() -> list[ParallelTools | MCPTools]:
    if getenv("PARALLEL_API_KEY"):
        return [ParallelTools()]
    # timeout_seconds: web_fetch page extraction regularly exceeds the 10s MCP default.
    return [
        MCPTools(
            url="https://search.parallel.ai/mcp",
            transport="streamable-http",
            name="parallel_tools",
            timeout_seconds=30,
        )
    ]


def get_slack_tools() -> list[SlackTools]:
    """Toolkit Slack con scope di invio, solo quando l'interfaccia Slack è configurata.

    Deliberatamente più ristretto delle impostazioni predefinite di SlackTools: un registro da cui qualsiasi agno
    può attingere ottiene invio messaggi + elenco canali, mai letture della cronologia o trasferimento file.
    """
    if not getenv("SLACK_BOT_TOKEN"):
        return []
    return [
        SlackTools(
            token=getenv("SLACK_BOT_TOKEN"),
            enable_send_message=True,
            enable_send_message_thread=True,
            enable_list_channels=True,
            enable_get_channel_history=False,
            enable_upload_file=False,
            enable_download_file=False,
        )
    ]


def get_media_tools() -> list[OpenAITools]:
    """Generazione immagini e testo-a-vocalizzazione sulla chiave OpenAI esistente della piattaforma.

    I media generati tornano come artifact di esecuzione (byte sulla RunResponse), quindi
    persistono in Postgres e sopravvivono ai filesystem effimeri dei container. La trascrizione
    è disabilitata: transcribe_audio legge percorsi di file locali al server, che gli agenti di questa
    piattaforma non hanno mai.
    """
    # OpenAITools raises without the key; the registry import must not.
    if not getenv("OPENAI_API_KEY"):
        return []
    return [OpenAITools(enable_transcription=False, image_model="gpt-image-2")]


def get_file_generation_tools() -> list[FileGenerationTools]:
    """File scaricabili (JSON, CSV, TXT, HTML, codice) come artifact di esecuzione in memoria."""
    return [FileGenerationTools(enable_pdf_generation=False, enable_docx_generation=False)]


def get_knowledge_management_tools() -> KnowledgeManagementTools:
    """Il lato di scrittura della knowledge base di prodotto, montato su Platform Builder."""
    return KnowledgeManagementTools(knowledge=product_knowledge)
