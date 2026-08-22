# ---------------------------------------------------------------------------
# Brute-Force Authentication Training Lab — production image (ASGI/Daphne)
# ---------------------------------------------------------------------------
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    DJANGO_SETTINGS_MODULE=config.settings.prod

WORKDIR /app

# System deps: build tools for psycopg + curl for healthchecks.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
# Install runtime deps plus the PostgreSQL driver (uncommented for the image).
RUN pip install -r requirements.txt "psycopg[binary]==3.2.4"

COPY . .

# Collect static files at build time (needs a dummy secret; DEBUG stays off).
RUN SECRET_KEY=build-time-dummy-key DJANGO_SETTINGS_MODULE=config.settings.base \
    python manage.py collectstatic --noinput

EXPOSE 8000

# Run migrations then serve HTTP + WebSockets via Daphne (ASGI).
CMD ["sh", "-c", "python manage.py migrate --noinput && daphne -b 0.0.0.0 -p 8000 config.asgi:application"]
