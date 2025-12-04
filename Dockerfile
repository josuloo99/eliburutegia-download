FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --shell /bin/bash botuser || true

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=botuser:botuser . .

RUN mkdir -p /app/logs && chown -R botuser:botuser /app/logs

USER botuser

VOLUME ["/app/downloads"]

CMD ["python", "main.py"]