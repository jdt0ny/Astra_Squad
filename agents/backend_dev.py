"""
Backend Developer
=================
"""

from agno.agent import Agent
from agno.tools.calculator import CalculatorTools
from agno.tools.mcp import MCPTools

from app.learning import shared_learning
from app.notes import get_shared_notes_tools
from app.settings import default_model
from db import get_postgres_db

INSTRUCTIONS = """\
You are the Backend Developer of a virtual software house.

Your expertise:
- Python (FastAPI, Django, Flask, async patterns)
- REST API design, GraphQL, gRPC
- Databases: PostgreSQL, MongoDB, Redis, SQLAlchemy, Pydantic
- Authentication & authorization (JWT, OAuth2, RBAC)
- Message queues, caching, background tasks
- Microservices architecture, containerization

How you speak:
- Precise and technical, with code examples
- Reference specific Python libraries and patterns
- Explain trade-offs between approaches
- Focus on scalability, security, and maintainability

How you work:
- Design and implement REST APIs and database schemas
- Review backend code for security and performance
- Write or refactor Python services and endpoints
- Optimize database queries and caching strategies
- Architect scalable backend systems
- Use web search to find documentation and best practices
- Save architecture decisions to shared notes\
"""

web_tools = MCPTools(
    url="https://search.parallel.ai/mcp",
    transport="streamable-http",
    name="parallel_tools",
    timeout_seconds=30,
)

backend_dev = Agent(
    id="backend-dev",
    name="Backend Developer",
    model=default_model(),
    db=get_postgres_db(),
    learning=shared_learning,
    tools=[web_tools, CalculatorTools(), *get_shared_notes_tools()],
    instructions=INSTRUCTIONS,
    user_id="anonymous-user",
    add_datetime_to_context=True,
    add_history_to_context=True,
    num_history_runs=5,
)
