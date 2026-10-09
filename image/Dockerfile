# CloakBrowser base, built from the jonclegg/CloakBrowser fork by the
# `cloakbrowser` service in docker-compose.yml.
FROM cloakbrowser

RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends tzdata x11vnc novnc websockify \
    && rm -rf /var/lib/apt/lists/*

# `cloakroom share`: a Cloudflare quick tunnel to the viewer, run by the chat API so
# a run that needs the user can hand them a link. The host needs nothing for it.
ARG TARGETARCH
RUN curl -fsSL --retry 3 -o /usr/local/bin/cloudflared \
        "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-${TARGETARCH}" \
    && chmod +x /usr/local/bin/cloudflared \
    && cloudflared --version

# The browser: Fury's patched Chromium, built for Linux from the jonclegg fork
# (branch linux-build). cloakserve still runs the pool, GeoIP and native input;
# CLOAKBROWSER_BINARY_PATH makes it launch fury-chrome, which hands the core a
# persona config instead of CloakBrowser's --fingerprint flags.
ARG FURY_CORE_URL=https://github.com/jonclegg/fury-antidetect-browser/releases/download/core-155.0.8059.12-linux.1
ARG FURY_CORE_SHA256_AMD64=c725e4ba03945b3dd8aab72924771d9b0b6589960a083ad7c3ac35e6bcc921b6
ARG FURY_CORE_SHA256_ARM64=b91057c0dfd436aabefcccec1c52fe340308196cdd9d98a72ae1742b47143745
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends xz-utils \
    && rm -rf /var/lib/apt/lists/* \
    && case "$TARGETARCH" in \
         amd64) arch=x64; sha="$FURY_CORE_SHA256_AMD64" ;; \
         arm64) arch=arm64; sha="$FURY_CORE_SHA256_ARM64" ;; \
       esac \
    && curl -fsSL --retry 3 -o /tmp/fury-core.tar.xz "$FURY_CORE_URL/fury-core-linux-$arch.tar.xz" \
    && echo "$sha  /tmp/fury-core.tar.xz" | sha256sum -c - \
    && tar -xJf /tmp/fury-core.tar.xz -C /opt \
    && mv /opt/Fury /opt/fury \
    && rm /tmp/fury-core.tar.xz \
    && /opt/fury/chrome --version
COPY fury-personas.json /opt/fury/personas.json
COPY fury-chrome /usr/local/bin/fury-chrome
# CLOAKBROWSER_VERSION is what cloakserve gates its window settling on. Settling
# exists for CloakBrowser builds before 148 that report an incoherent window;
# with it on, Fury's Mac persona (a 33 px menu bar the X11 window cannot know
# about) fails every size and the launch is killed. fury-chrome places the
# window on the persona's available area instead.
ENV CLOAKBROWSER_BINARY_PATH=/usr/local/bin/fury-chrome \
    CLOAKBROWSER_VERSION=155.0.8059.12

COPY index.html /usr/share/novnc/index.html
# Safari can keep a cached noVNC <=1.3 ui.js, which crashes on load if this
# element is missing (upstream removed it in 1.4). Newer ui.js ignores it. Inline
# display:none, because noVNC's CSS overrides the hidden attribute on inputs.
RUN sed -i 's#<textarea id="noVNC_clipboard_text" rows=5></textarea>#&\n                <input id="noVNC_clipboard_clear_button" type="button" style="display:none">#' /usr/share/novnc/vnc.html \
    && grep -q 'id="noVNC_clipboard_clear_button"' /usr/share/novnc/vnc.html
COPY cloakroom-serve.sh /usr/local/bin/cloakroom-serve
# `docker exec cloakroom cloakroom chat|key|smoke|share|status ...` works from any host
# shell (macOS, Linux, PowerShell), with nothing installed on the host.
COPY cloakroom-client.sh /usr/local/bin/cloakroom
RUN chmod +x /usr/local/bin/cloakroom-serve /usr/local/bin/cloakroom /usr/local/bin/fury-chrome

# The chat API and its DeepSeek agent. The base image already has Python and
# Playwright; the API uses only the standard library on top of them.
COPY --from=agent *.py console.html /opt/cloakroom/agent/
COPY --from=agent guidance /opt/cloakroom/agent/guidance
COPY --from=examples humanize.py bing_first.py /opt/cloakroom/examples/
ENV CLOAKROOM_EXAMPLES=/opt/cloakroom/examples \
    CLOAKROOM_DATA=/data
LABEL org.opencontainers.image.source=https://github.com/jonclegg/cloakroom \
      org.opencontainers.image.description="Cloakroom: a stealth browser for AI agents" \
      org.opencontainers.image.licenses=MIT

EXPOSE 9222 6080 8423

CMD ["cloakroom-serve"]
