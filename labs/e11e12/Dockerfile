ARG BASE_IMAGE=python:3.13-slim@sha256:f82c96458eedc847b233e582eb31336f4954b39cae020b6dcf5b3ed0e5cbcd74
ARG DOCKER_CLI_IMAGE=docker:28.5.1-cli@sha256:9190b0613792e658a7783cf14b2d5ace5941bb68ede7276922ea36ee457d76ad
FROM ${DOCKER_CLI_IMAGE} AS docker-cli
FROM ${BASE_IMAGE}
ARG DEBIAN_ORIGIN=https://deb.debian.org

ENV LC_ALL=C.UTF-8 TZ=UTC PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN sed -Ei "s|https?://deb.debian.org|${DEBIAN_ORIGIN%/}|g" /etc/apt/sources.list.d/debian.sources \
 && apt-get -o APT::Update::Error-Mode=any update \
 && apt-get install -y --no-install-recommends gcc make libc6-dev git strace \
 && dpkg-query -W -f='${Package}=${Version}\n' gcc make libc6-dev git strace > /opt/toolchain.lock \
 && rm -rf /var/lib/apt/lists/*

COPY --from=docker-cli /usr/local/bin/docker /usr/local/bin/docker
COPY --from=docker-cli /usr/local/libexec/docker/cli-plugins/docker-buildx /usr/local/libexec/docker/cli-plugins/docker-buildx
