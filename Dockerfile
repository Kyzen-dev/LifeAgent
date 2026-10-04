FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    # Persist ~/.claude (session transcripts for resume) and Google OAuth tokens.
    HOME=/data/home \
    LIFEAGENT_DATA_DIR=/data \
    LIFEAGENT_WORKSPACE_DIR=/app/workspace

# git/ripgrep help the agent's built-in tools; uv provides `uvx` for the Google Workspace MCP server.
RUN apt-get update \
    && apt-get install -y --no-install-recommends git ripgrep ca-certificates curl \
    && rm -rf /var/lib/apt/lists/* \
    && pip install uv matplotlib

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY lifeagent ./lifeagent
COPY workspace ./workspace

# Run as an unprivileged user.
RUN useradd -m -u 1000 agent && mkdir -p /data/home && chown -R agent:agent /app /data
USER agent

CMD ["python", "-m", "lifeagent"]
