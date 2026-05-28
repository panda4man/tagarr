# plex-labeling — Copilot Instructions

## Project overview

Tiny Flask service that listens for Plex Pass webhooks and auto-applies labels to newly added Movies and TV Shows via `python-plexapi`. Labels are **additively merged** — existing labels are never removed.

## Running the service

```bash
# Build and run (primary workflow)
docker compose up --build -d

# Local dev (requires a valid config/config.yaml)
pip install -r requirements.txt
python -m app.main
```

There are no tests or linters configured in this project.

## Smoke-testing the webhook

```bash
curl -X POST http://localhost:8080/webhook \
  -F 'payload={"event":"library.new","Metadata":{"librarySectionType":"movie","ratingKey":"REAL_RATING_KEY"}}'
```

Use a real `ratingKey` from your Plex library. The endpoint always returns HTTP 200 — Plex requires this.

## Architecture

```
app/main.py      — Flask app factory (create_app) + Waitress entry point
app/config.py    — Loads YAML config, env vars override config values
app/labeler.py   — Fetches Plex item by ratingKey, computes label diff, calls item.addLabel()
app/logs.py      — Sets up rotating file handler + stdout stream handler
config/          — Mount point for config.yaml (read-only in Docker)
```

`create_app()` in `main.py` wires everything together: load config → init logging → connect to PlexServer → register webhook route(s). The `PlexServer` instance is captured in the closure, shared across requests.

## Configuration

Config is a YAML file (`config/config.yaml`) with env var overrides. Copy from `config/config.example.yaml`.

| Env var | Overrides |
|---|---|
| `PLEX_URL` | `plex.url` |
| `PLEX_TOKEN` | `plex.token` |
| `CONFIG_PATH` | Path to YAML (default `/config/config.yaml`) |
| `LOG_LEVEL` | `logging.level` |
| `WEBHOOK_TOKEN` | If set, changes the webhook path to `/webhook/<token>` |
| `BIND_HOST` / `BIND_PORT` | Listen address (default `0.0.0.0:8080`) |

Never commit a real `config.yaml` — it contains the Plex auth token. Use `.env` for `PLEX_TOKEN` locally.

## Key conventions

- **Webhook always returns 200.** Plex doesn't retry on non-2xx, so error handling logs exceptions and returns empty 200 rather than propagating errors.
- **Label merging is additive.** `apply_labels` computes `to_add = [l for l in labels if l not in existing]` and only calls `item.addLabel(to_add)` when there's something new.
- **Only `library.new` events trigger labeling.** All other event types are silently ignored with a DEBUG log.
- **`library_types` filter** (`movie`, `show` by default) gates which Plex library sections are acted on. This matches the `librarySectionType` field in the webhook payload.
- **Entry point:** `python -m app.main` calls `main()`, which calls `create_app()` then `waitress.serve()`.
