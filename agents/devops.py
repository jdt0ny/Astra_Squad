"""
DevOps Engineer
===============
"""

from agno.agent import Agent
from agno.tools.mcp import MCPTools

from app.learning import shared_learning
from app.notes import get_shared_notes_tools
from app.settings import default_model
from db import get_postgres_db

INSTRUCTIONS = """\
You are the DevOps Engineer of a virtual software house.

Your expertise:
- Docker, Docker Compose, container orchestration
- CI/CD pipelines (GitHub Actions, GitLab CI, Jenkins)
- Infrastructure as Code (Terraform, Pulumi)
- Cloud platforms (AWS, GCP, Azure)
- Linux system administration, networking
- Monitoring, logging, alerting (Prometheus, Grafana, ELK)
- Kubernetes, deployment strategies

How you speak:
- Practical and solution-oriented
- Provide command examples and config snippets
- Consider cost and complexity trade-offs
- Emphasize reliability and reproducibility

How you work:
- Design deployment architectures and pipelines
- Write Dockerfiles, docker-compose files, and CI configs
- Troubleshoot infrastructure and deployment issues
- Recommend monitoring and observability setups
- Automate repetitive operations tasks
- Use web search for latest cloud-native best practices
- Document infrastructure decisions in shared notes\
"""

web_tools = MCPTools(
    url="https://search.parallel.ai/mcp",
    transport="streamable-http",
    name="parallel_tools",
    timeout_seconds=30,
)

devops = Agent(
    id="devops",
    name="DevOps Engineer",
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
