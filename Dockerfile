# Portable production image — works on Fly.io, Railway, HF Spaces, GCP Cloud Run, etc.
# Build:  docker build -t stock-research-lab .
# Run:    docker run -p 8000:8000 stock-research-lab

FROM python:3.11-slim-bookworm

# --- System deps kept to a minimum
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    TZ=Asia/Kolkata

# build-essential covers the (rare) wheel that needs to compile.
# libxml2/libxslt are runtime deps for trafilatura.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libxml2 \
        libxslt1.1 \
        ca-certificates \
        tzdata \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /srv/app

# Install deps first (cache layer) — only requirements-prod.txt is needed
COPY requirements-prod.txt ./
RUN pip install --upgrade pip && pip install -r requirements-prod.txt

# Then the app code
COPY pyproject.toml ./
COPY app/ ./app/
COPY web/ ./web/
RUN pip install -e . --no-deps

# Ensure cache dirs exist and are writable
RUN mkdir -p data/cache data/processed data/raw

EXPOSE 8000

# PORT is set by most PaaS providers; default to 8000 for local Docker runs.
ENV PORT=8000
CMD ["sh", "-c", "uvicorn app.api.server:app --host 0.0.0.0 --port ${PORT:-8000}"]
