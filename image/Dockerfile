# CloakBrowser base, built from the jonclegg/CloakBrowser fork by the
# `cloakbrowser` service in docker-compose.yml.
FROM cloakbrowser

RUN apt-get update \
    && apt-get install -y --no-install-recommends x11vnc novnc websockify \
    && rm -rf /var/lib/apt/lists/*

COPY index.html /usr/share/novnc/index.html
COPY cloakroom-serve.sh /usr/local/bin/cloakroom-serve
RUN chmod +x /usr/local/bin/cloakroom-serve

EXPOSE 9222 6080

CMD ["cloakroom-serve"]
