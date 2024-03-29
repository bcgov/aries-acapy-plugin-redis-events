FROM bcgovimages/von-image:py36-1.16-1

RUN pip3 install --no-cache-dir poetry

USER root

# Add docker-compose-wait tool
ENV WAIT_VERSION 2.7.2
ADD https://github.com/ufoscout/docker-compose-wait/releases/download/$WAIT_VERSION/wait /wait
RUN chmod +x /wait

RUN mkdir redis_queue && touch redis_queue/__init__.py

COPY ./README.md ./setup.py ./pyproject.toml ./poetry.lock ./
USER root
RUN chown indy:indy -R .
USER indy

RUN poetry install --no-dev

# Make site packages location more accessible (for use with volumes)
RUN ln -s $(poetry env info -p)/lib/python3.6/site-packages site-packages

COPY redis_queue redis_queue
COPY ./docker/default.yml .
COPY ./docker/plugins-config.yml .

ENTRYPOINT ["/bin/sh", "-c", "/wait && poetry run aca-py \"$@\"", "--"]
CMD ["start",  "--plugin", "redis_queue", "--plugin-config", "plugins-config.yml", "--arg-file", "default.yml"]
