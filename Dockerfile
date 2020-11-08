FROM benediktkr/poetry:latest
MAINTAINER Benedikt Kristinsson <benedikt@lokun.is>

RUN useradd -u 1211 -ms /bin/bash zflux

# RUN mkdir /zflux
# COPY zflux/ /zflux/zflux/
# COPY tests/ /zlux/tests/
# COPY pyproject.toml /zflux/pyproject.toml
# COPY poetry.lock /zflux/poetry.lock

#RUN pip install /zflux

# idea is to override with bind mounts
# since config.py doesnt do env vars as-is


COPY --from=build-zflux /usr/local/lib/python3.8/site-packages/ /usr/local/lib/python3.8/site-packages/
WORKDIR /app
COPY pyproject.toml poetry.lock /app/
COPY zflux/ /app/zflux/
RUN poetry install --no-dev

ENV ZFLUX_CONF "/etc/zflux.yml"
EXPOSE 5558
USER 1211

CMD ["zflux"]
