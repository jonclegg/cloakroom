FROM cloakhq/cloakbrowser:latest

RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends tzdata x11vnc novnc websockify \
    && rm -rf /var/lib/apt/lists/*

COPY index.html /usr/share/novnc/index.html
COPY cloakserve-headed.py /usr/local/bin/cloakserve-headed.py
COPY cloakroom-serve.sh /usr/local/bin/cloakroom-serve
RUN chmod +x /usr/local/bin/cloakroom-serve

# The chat API and its DeepSeek agent. The base image already has Python and
# Playwright; the API uses only the standard library on top of them.
COPY --from=agent *.py /opt/cloakroom/agent/
COPY --from=agent guidance /opt/cloakroom/agent/guidance
COPY --from=examples humanize.py bing_first.py /opt/cloakroom/examples/
ENV CLOAKROOM_EXAMPLES=/opt/cloakroom/examples \
    CLOAKROOM_DATA=/data

EXPOSE 9222 6080 8423

CMD ["cloakroom-serve"]
