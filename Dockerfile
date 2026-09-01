FROM python:3.12.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080

RUN addgroup --system watchtower && adduser --system --ingroup watchtower watchtower

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir --requirement requirements.txt

COPY pyproject.toml README.md ./
COPY watchtower ./watchtower
RUN pip install --no-cache-dir --no-deps .

USER watchtower
EXPOSE 8080
CMD ["sh", "-c", "uvicorn watchtower.api:app --host 0.0.0.0 --port ${PORT:-8080}"]
