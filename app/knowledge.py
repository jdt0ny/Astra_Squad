"""
Knowledge della Piattaforma
============================

Due basi di conoscenza PgVector disponibili per i componenti della piattaforma:

- shared-knowledge: una base di conoscenza condivisa che può essere utilizzata da qualsiasi componente.
  Carica documenti tramite l'interfaccia AgentOS o l'API `/knowledge`.
- product-knowledge: una base di conoscenza dedicata per gli agenti di prodotto.
"""

from __future__ import annotations

from agno.knowledge import Knowledge

from db import create_knowledge

KNOWLEDGE_NAME = "shared-knowledge"
PRODUCT_KNOWLEDGE_NAME = "product-knowledge"

shared_knowledge: Knowledge = create_knowledge(
    name=KNOWLEDGE_NAME,
    table_name="shared_knowledge",
)

product_knowledge: Knowledge = create_knowledge(
    name=PRODUCT_KNOWLEDGE_NAME,
    table_name="product_knowledge",
)
