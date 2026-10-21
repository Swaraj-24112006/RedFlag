.PHONY: help up down build migrate seed test lint run

help:
	@echo "KSPG RedFlag Backend Makefile Commands:"
	@echo "  make up       - Start all Docker containers (Postgres, MinIO, Backend)"
	@echo "  make down     - Stop all Docker containers"
	@echo "  make build    - Rebuild Docker images"
	@echo "  make migrate  - Run database migrations"
	@echo "  make seed     - Seed master data and demo users"
	@echo "  make test     - Run pytest test suite"
	@echo "  make lint     - Run Ruff linter"
	@echo "  make run      - Run Django dev server locally (Python)"

up:
	docker compose up -d

down:
	docker compose down

build:
	docker compose build

migrate:
	python manage.py migrate

seed:
	python manage.py seed_masterdata
	python manage.py seed_demo_users

test:
	pytest

lint:
	ruff check .

run:
	python manage.py runserver 0.0.0.0:8000
