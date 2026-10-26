# syntax=docker/dockerfile:1

# === Base image with Python and user setup ===
FROM python:3.14-slim AS base
COPY --from=docker.io/astral/uv:latest /uv /uvx /bin/

ARG USERNAME=pyuser
ARG GROUPNAME=pyuser
ARG UID=1000
ARG GID=1000

WORKDIR /code

RUN groupadd -g ${GID} ${GROUPNAME} && \
    useradd -m -u ${UID} -g ${GID} -s /bin/bash ${USERNAME}
RUN chown ${USERNAME}:${GROUPNAME} /code
USER ${USERNAME}

COPY pyproject.toml uv.lock ./
COPY --chown=${USERNAME}:${GROUPNAME} . .

RUN echo "source /code/.venv/bin/activate" >> /home/pyuser/.bashrc

# === Production image ===
FROM base AS production

ENV VIRTUAL_ENV="/code/.venv"
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

RUN uv sync --no-dev --frozen

CMD ["sh", "-c", "COLUMNS=120 exec wgcd run -d /var/mnt -l /var/repositories.txt"]
