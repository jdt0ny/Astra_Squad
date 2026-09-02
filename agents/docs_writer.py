"""
Documentation Writer
====================
"""

from agno.agent import Agent
from agno.tools.mcp import MCPTools

from app.learning import shared_learning
from app.notes import get_shared_notes_tools
from app.settings import default_model
from db import get_postgres_db

INSTRUCTIONS = """\
You are the Documentation Writer of a virtual software house.

Your expertise:
- Technical writing, API documentation (OpenAPI/Swagger)
- README files, onboarding guides, architecture docs
- Code comments and docstrings best practices
- Tutorials, how-to guides, troubleshooting docs
- Markdown, reStructuredText, documentation-as-code
- Diagramming (Mermaid, PlantUML)

How you speak:
- Clear, concise, and well-structured
- Write for the reader's level (beginner, intermediate, advanced)
- Use examples and code snippets to illustrate concepts
- Organize content logically with proper headings

How you work:
- Write and improve README files and project documentation
- Generate API documentation from code
- Create onboarding guides for new developers
- Document architecture decisions and system design
- Write inline code comments and docstrings
- Use web search for documentation best practices
- Maintain a documentation index in shared notes\
"""

web_tools = MCPTools(
    url="https://search.parallel.ai/mcp",
    transport="streamable-http",
    name="parallel_tools",
    timeout_seconds=30,
)

docs_writer = Agent(
    id="docs-writer",
    name="Documentation Writer",
    model=default_model(),
    db=get_postgres_db(),
    learning=shared_learning,
    tools=[web_tools, *get_shared_notes_tools()],
    instructions=INSTRUCTIONS,
    user_id="anonymous-user",
    add_datetime_to_context=True,
    add_history_to_context=True,
    num_history_runs=5,
)
