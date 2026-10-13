ARG BUILD_FROM=python:3.12-slim-bookworm
FROM ${BUILD_FROM}

# Pinned commit of https://github.com/inkbox-ai/claude-code-plugin
ARG INKBOX_CLAUDE_REF=a02722d42bbdc40e8a6944fccf4118c594dd5661

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl ffmpeg git jq \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m venv /opt/inkbox-claude \
    && /opt/inkbox-claude/bin/pip install --no-cache-dir --upgrade pip \
    && /opt/inkbox-claude/bin/pip install --no-cache-dir \
       "claude-code-plugin @ git+https://github.com/inkbox-ai/claude-code-plugin@${INKBOX_CLAUDE_REF}" \
       "caldav==3.4.0" "faster-whisper==1.2.1" tzdata

# The Agent SDK ships a native Claude Code binary; expose it as `claude` so
# doctor and the readiness check find it.
RUN bundled="$(/opt/inkbox-claude/bin/python -c 'import claude_agent_sdk, os; print(os.path.join(os.path.dirname(claude_agent_sdk.__file__), "_bundled", "claude"))')" \
    && test -x "$bundled" \
    && ln -s "$bundled" /usr/local/bin/claude \
    && claude --version

ENV PATH="/opt/inkbox-claude/bin:${PATH}"

COPY run.sh /run.sh
COPY apple-calendar transcribe downloader ha-addons ebay druck krypto pakete untis claude-bridge /usr/local/bin/
RUN chmod +x /run.sh /usr/local/bin/apple-calendar /usr/local/bin/transcribe /usr/local/bin/downloader /usr/local/bin/ha-addons /usr/local/bin/ebay /usr/local/bin/druck /usr/local/bin/krypto /usr/local/bin/pakete /usr/local/bin/untis /usr/local/bin/claude-bridge

CMD ["/run.sh"]
