FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src

RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir . \
    && groupadd --gid 1000 rasterreg \
    && useradd --uid 1000 --gid rasterreg --create-home \
        --shell /usr/sbin/nologin rasterreg \
    && mkdir /data \
    && chown rasterreg:rasterreg /data

USER rasterreg
WORKDIR /data

ENTRYPOINT ["rasterreg"]
