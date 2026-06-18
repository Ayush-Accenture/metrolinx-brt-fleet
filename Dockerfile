# BRT Fleet Movement Pipeline — Production Image
# Includes: fleet-agents, soti_mcp_server, brampton_mcp_server
# Built from repo root: az acr build --registry agenticaidashboardacr --image brt-fleet-pipeline:latest .

FROM python:3.13-slim

# System deps for openpyxl/pandas/cryptography + Azure SDK
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libffi-dev \
    libssl-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ── Install pipeline dependencies ──────────────────────────────────────────
COPY fleet-agents/requirements.txt fleet-agents/requirements.txt
RUN pip install --no-cache-dir -r fleet-agents/requirements.txt

# ── Install SOTI MCP server dependencies ───────────────────────────────────
COPY soti_mcp_server/requirements.txt soti_mcp_server/requirements.txt
RUN pip install --no-cache-dir -r soti_mcp_server/requirements.txt

# ── Install Brampton MCP server dependencies ───────────────────────────────
COPY brampton_mcp_server/requirements.txt brampton_mcp_server/requirements.txt
RUN pip install --no-cache-dir -r brampton_mcp_server/requirements.txt

# ── Copy source code ───────────────────────────────────────────────────────
COPY fleet-agents/ fleet-agents/
COPY soti_mcp_server/ soti_mcp_server/
COPY brampton_mcp_server/ brampton_mcp_server/

# Working directory for the pipeline entrypoint
WORKDIR /app/fleet-agents

# Env defaults
ENV PYTHONUTF8=1
ENV PYTHONUNBUFFERED=1
# Point SOTI MCP CWD to the container path (overrides the Windows path default in config.py)
ENV SOTI_MCP_CWD=/app/soti_mcp_server

# All secrets/flags injected at Container Apps Job runtime
# e.g. USE_MOCK_SOTI, USE_MOCK_LLM, COSMOS_CONNECTION_STRING, etc.

ENTRYPOINT ["python", "run.py"]
CMD ["--help"]
