# Common tasks. See README.md for details.
COMPOSE = docker compose -f infra/docker-compose.yml

up:            ## Build and start Postgres, the API and the dashboard
	$(COMPOSE) up --build -d
down:          ## Stop everything (keeps data)
	$(COMPOSE) down
reset:         ## Stop everything and delete the database
	$(COMPOSE) down -v
test:          ## API tests against the Postgres from `make up` (creates and drops ondra_test)
	uv run pytest -q
migrate:       ## Apply migrations to the local database
	cd apps/api && uv run alembic upgrade head
seed:          ## Add the example dealership if the database is empty
	cd apps/api && uv run python -m ondra_api.seed --if-empty
.PHONY: up down reset test migrate seed
