# trixie: provides fonts-vazirmatn (Persian font for PDF/Word/charts)
FROM python:3.12-slim-trixie

# Set to true to enable the optional headless browser (Playwright MCP): ~400 MB larger image.
ARG INSTALL_BROWSER=false

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    # Persist ~/.claude (session transcripts for resume) and Google OAuth tokens.
    HOME=/data/home \
    LIFEAGENT_DATA_DIR=/data \
    LIFEAGENT_WORKSPACE_DIR=/app/workspace

# git/ripgrep: the agent's built-in tools · pango + fonts: PDF and charts with Persian text
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        git ripgrep ca-certificates curl fontconfig \
        fonts-vazirmatn fonts-dejavu-core libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz-subset0 \
    && if [ "$INSTALL_BROWSER" = "true" ]; then \
        apt-get install -y --no-install-recommends nodejs npm chromium; fi \
    && rm -rf /var/lib/apt/lists/* \
    && fc-cache -f

WORKDIR /app
COPY requirements.txt requirements-docs.txt ./
# uv provides `uvx` for the Google Workspace MCP server.
RUN pip install uv -r requirements.txt -r requirements-docs.txt

COPY lifeagent ./lifeagent
COPY workspace ./workspace

# Run as an unprivileged user.
RUN useradd -m -u 1000 agent && mkdir -p /data/home && chown -R agent:agent /app /data
USER agent

CMD ["python", "-m", "lifeagent"]
