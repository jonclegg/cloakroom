FROM cloakhq/cloakbrowser:latest

RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends tzdata x11vnc novnc websockify \
    && rm -rf /var/lib/apt/lists/*

# novnc 1.6 dropped noVNC_clipboard_clear_button, but browsers (Safari especially)
# can keep an older cached app/ui.js that still binds it and throws on null.
RUN sed -i 's|<textarea id="noVNC_clipboard_text" rows=5></textarea>|&\n                <input id="noVNC_clipboard_clear_button" type="button" hidden>|' /usr/share/novnc/vnc.html \
    && grep -q 'id="noVNC_clipboard_clear_button"' /usr/share/novnc/vnc.html

COPY index.html /usr/share/novnc/index.html
COPY cloakserve-headed.py /usr/local/bin/cloakserve-headed.py
COPY cloakroom-serve.sh /usr/local/bin/cloakroom-serve
RUN chmod +x /usr/local/bin/cloakroom-serve

EXPOSE 9222 6080

CMD ["cloakroom-serve"]
