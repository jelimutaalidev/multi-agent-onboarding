.PHONY: install test run api docker-build docker-up lint clean

install:
	pip install -r requirements.txt

test:
	python -m pytest tests/ -v -m "not integration" --tb=short

run:
	python api.py

api:
	python api.py 0.0.0.0 8000

docker-build:
	docker compose build

docker-up:
	docker compose up -d

docker-down:
	docker compose down

docker-logs:
	docker compose logs -f

lint:
	ruff check src/ tests/

typecheck:
	mypy src/

format:
	ruff format src/ tests/

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null; \
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null; \
	find . -type f -name "*.pyc" -delete 2>/dev/null; \
	find . -type f -name "*.pyo" -delete 2>/dev/null

all: install test
