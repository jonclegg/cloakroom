# CloakBrowser base, built from the jonclegg/CloakBrowser fork by the
# `cloakbrowser` service in docker-compose.yml.
FROM cloakbrowser

RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends tzdata x11vnc novnc websockify \
    && rm -rf /var/lib/apt/lists/*

COPY index.html /usr/share/novnc/index.html
# Safari can keep a cached noVNC <=1.3 ui.js, which crashes on load if this
# element is missing (upstream removed it in 1.4). Newer ui.js ignores it. Inline
# display:none, because noVNC's CSS overrides the hidden attribute on inputs.
RUN sed -i 's#<textarea id="noVNC_clipboard_text" rows=5></textarea>#&\n                <input id="noVNC_clipboard_clear_button" type="button" style="display:none">#' /usr/share/novnc/vnc.html \
    && grep -q 'id="noVNC_clipboard_clear_button"' /usr/share/novnc/vnc.html
COPY cloakroom-serve.sh /usr/local/bin/cloakroom-serve
# `docker exec cloakroom cloakroom chat|key|smoke|status ...` works from any host
# shell (macOS, Linux, PowerShell), with nothing installed on the host.
COPY cloakroom-client.sh /usr/local/bin/cloakroom
RUN chmod +x /usr/local/bin/cloakroom-serve /usr/local/bin/cloakroom

# The chat API and its DeepSeek agent. The base image already has Python and
# Playwright; the API uses only the standard library on top of them.
COPY --from=agent *.py /opt/cloakroom/agent/
COPY --from=agent guidance /opt/cloakroom/agent/guidance
COPY --from=examples humanize.py bing_first.py /opt/cloakroom/examples/
ENV CLOAKROOM_EXAMPLES=/opt/cloakroom/examples \
    CLOAKROOM_DATA=/data
LABEL org.opencontainers.image.source=https://github.com/jonclegg/cloakroom \
      org.opencontainers.image.description="Cloakroom: a stealth browser for AI agents" \
      org.opencontainers.image.licenses=MIT

EXPOSE 9222 6080 8423

CMD ["cloakroom-serve"]
