.PHONY: run ui web test install clean docker-build docker-run prod-install

TICKER ?= RELIANCE
TIMEFRAME ?= 6mo
PORT ?= 8000

install:
	pip install -e .[dev]

# Slim production install — same set of deps the cloud build uses.
prod-install:
	pip install -r requirements-prod.txt && pip install -e . --no-deps

# Build the production Docker image locally.
docker-build:
	docker build -t stock-research-lab .

# Run the production Docker image locally — sanity check before pushing to any host.
docker-run:
	docker run --rm -p $(PORT):8000 stock-research-lab

run:
	python -m app.main --ticker $(TICKER) --timeframe $(TIMEFRAME)

ui:
	streamlit run app/ui/streamlit_app.py

# New web UI — vanilla HTML/CSS/JS served by FastAPI/uvicorn.
# Open http://localhost:$(PORT)
web:
	uvicorn app.api.server:app --reload --port $(PORT)

test:
	pytest -q

clean:
	rm -rf data/cache/* data/raw/* data/processed/*
	find . -type d -name __pycache__ -exec rm -rf {} +
