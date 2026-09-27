FROM cloakhq/cloakbrowser:latest

RUN apt-get update \
    && apt-get install -y --no-install-recommends x11vnc novnc websockify \
    && rm -rf /var/lib/apt/lists/*

COPY index.html /usr/share/novnc/index.html
# Safari can keep a cached noVNC <=1.3 ui.js, which crashes on load if this
# element is missing (upstream removed it in 1.4). Hidden, so newer ui.js ignores it.
RUN sed -i 's#<textarea id="noVNC_clipboard_text" rows=5></textarea>#&\n                <input id="noVNC_clipboard_clear_button" type="button" hidden>#' /usr/share/novnc/vnc.html \
    && grep -q 'id="noVNC_clipboard_clear_button"' /usr/share/novnc/vnc.html
COPY cloakserve-headed.py /usr/local/bin/cloakserve-headed.py
COPY cloakroom-serve.sh /usr/local/bin/cloakroom-serve
RUN chmod +x /usr/local/bin/cloakroom-serve

EXPOSE 9222 6080

CMD ["cloakroom-serve"]
