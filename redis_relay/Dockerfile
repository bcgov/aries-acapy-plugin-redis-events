FROM python:3.7-alpine AS base
WORKDIR /usr/src/app
RUN apk update && \
  apk add \
  build-base \
  curl \
  git \
  libffi-dev \
  openssh-client \
  postgresql-dev

ENV POETRY_HOME=/opt/poetry \
  VENV=/usr/src/app/.venv
ENV PATH="$POETRY_HOME/bin:$VENV/bin:$PATH"

RUN curl -sSL https://raw.githubusercontent.com/python-poetry/poetry/master/install-poetry.py | python -
RUN poetry config virtualenvs.create true; poetry config virtualenvs.in-project true

COPY ./redis_relay/pyproject.toml ./redis_relay/poetry.lock ./
RUN mkdir ./relay && touch ./relay/relay.py
RUN poetry install

# Copy virtual environment into clean base
FROM python:3.7-alpine as main
WORKDIR /usr/src/app
COPY --from=base /usr/src/app /usr/src/app
ENV PATH="/usr/src/app/.venv/bin:$PATH"

# Add docker-compose-wait tool
ENV WAIT_VERSION 2.7.2
ADD https://github.com/ufoscout/docker-compose-wait/releases/download/$WAIT_VERSION/wait /wait
RUN chmod +x /wait

COPY redis_relay redis_relay
COPY status_endpoint status_endpoint
COPY redis_queue redis_queue
ENTRYPOINT ["/bin/sh", "-c", "/wait && python -m redis_relay.relay.relay \"$@\"", "--"]

