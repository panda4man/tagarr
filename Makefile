.PHONY: up down build test

up:
	docker compose up -d

down:
	docker compose down

build:
	docker compose build

test:
	pytest
