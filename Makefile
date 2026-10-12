# Docker (recommended)
up:            ## build and start the whole stack -> http://localhost:5180
	docker compose up --build -d
	@echo "Open http://localhost:5180  (demo: demo@tradeall.app / demo-trader-2026)"
down:
	docker compose down
logs:
	docker compose logs -f --tail=100 backend ingestor worker
reseed:        ## reload all market data, news and demo accounts
	docker compose exec backend python manage.py seed_demo --reset
	docker compose restart ingestor
test:          ## runs the backend test suite in a throwaway container
	docker compose run --rm --no-deps -e RUN_MIGRATIONS=0 backend sh -c "uv sync --frozen -q && pytest -q"
prod:          ## production-style build: nginx + built frontend -> http://localhost:8080
	docker compose -f docker-compose.yml -f docker-compose.prod.yml up --build -d

# Host development (Postgres/Redis still in Docker)
dev-infra:
	docker compose up -d db redis
dev-backend:
	cd backend && uv sync && .venv/bin/python manage.py migrate && .venv/bin/python manage.py seed_demo && .venv/bin/daphne -b 127.0.0.1 -p 8010 config.asgi:application
dev-ingestor:
	cd backend && .venv/bin/python manage.py run_ingestor
dev-frontend:
	cd frontend && npm install && npm run dev

.PHONY: up down logs reseed test prod dev-infra dev-backend dev-ingestor dev-frontend
