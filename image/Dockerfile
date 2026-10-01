FROM cloakhq/cloakbrowser:latest

RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends tzdata x11vnc novnc websockify \
    && rm -rf /var/lib/apt/lists/*

COPY index.html /usr/share/novnc/index.html
# Keep HTML/JS in sync (Debian novnc 1.6 dropped the clear button; Safari often
# caches an older ui.js that still expects noVNC_clipboard_clear_button).
COPY novnc-patch/vnc.html /usr/share/novnc/vnc.html
COPY novnc-patch/ui.js /usr/share/novnc/app/ui.js
COPY cloakserve-headed.py /usr/local/bin/cloakserve-headed.py
COPY cloakroom-serve.sh /usr/local/bin/cloakroom-serve
RUN chmod +x /usr/local/bin/cloakroom-serve

EXPOSE 9222 6080

CMD ["cloakroom-serve"]
