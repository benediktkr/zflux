FROM python:3.8
MAINTAINER Benedikt Kristinsson <benedikt@lokun.is>

RUN mkdir /zflux
COPY zflux/ /zflux/zflux/
COPY tests/ /zlux/tests/
COPY pyproject.toml /zflux/pyproject.toml
COPY poetry.lock /zflux/poetry.lock

RUN pip install /zflux

# idea is to override with bind mounts
# since config.py doesnt do env vars as-is
ENV ZFLUX_CONF "/zflux.yml"

EXPOSE 5559
ENTRYPOINT ["zflux"]
