FROM python:3.9 as base
MAINTAINER Benedikt Kristinsson <benedikt@lokun.is>

ENV DEBIAN_FRONTEND noninteractive
ENV TZ UTC
ENV TERM=xterm-256color

RUN useradd -u 1211 -ms /bin/bash zflux && \
        mkdir /zflux && \
        chown -R zflux. /zflux && \
        apt-get update && \
        apt-get install -y libzmq3-dev
RUN python -m pip install --upgrade pip
ENV PATH "/home/zflux/.local/bin:$PATH"
USER zflux

FROM base as builder

WORKDIR /zflux
RUN python -m pip install poetry

COPY .flake8 poetry.lock pyproject.toml /zflux/
RUN poetry install --no-interaction --ansi --no-root

COPY README.md /zflux/
COPY tests /zflux/tests/
COPY zflux /zflux/zflux/
COPY test-zflux-local.yml /zflux/test-zflux-local.yml

# should be in the jenkinsfile at some point

# this is shit
# RUN poetry run pytest
RUN poetry run isort . --check || true
RUN poetry run flake8 || true

RUN poetry build --no-interaction --ansi

FROM base as final

COPY --from=builder /zflux/dist/zflux-*.tar.gz /tmp
COPY --from=builder /zflux/dist/zflux-*.whl /tmp

# testing using the .whl file
RUN python -m pip install /tmp/zflux-*.whl && \
        rm /tmp/zflux-*.whl /tmp/zflux-*.tar.gz

HEALTHCHECK --start-period=5s --interval=15s --timeout=1s \
        CMD zf_ruok || exit 1

ENTRYPOINT ["zflux"]
