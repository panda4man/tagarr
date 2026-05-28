# plex-labeling — Copilot Instructions

## Project overview

Flask service that listens for webhooks from **Plex** and/or **Jellyfin** and auto-applies labels/tags to newly added Movies and TV content. At least one backend must be configured; both can run simultaneously. Labels are **additively merged** — existing labels are never removed.

## Running the service

```bash
# Build and run (primary workflow)
docker compose up --build -d

# Local dev (requires a valid config/config.yaml)
pip install -r requirements.txt
python -m app.main
```

## Running tests

```bash
pip install -r requirements-dev.txt
pytest                                              # full suite + coverage report
pytest tests/test_config.py                        # single file
pytest -k test_no_op_when_item_already_has_all_tags  # single test
```

## Smoke-testing the webhooks

```bash
# Plex
curl -X POST http://localhost:8080/webhook/plex \
  -F 'payload={"event":"library.new","Metadata":{"librarySectionType":"movie","ratingKey":"REAL_RATING_KEY"}}'

# Jellyfin
curl -X POST http://localhost:8080/webhook/jellyfin \
  -H 'Content-Type: application/json' \
  -d '{"NotificationType":"ItemAdded","ItemType":"Movie","ItemId":"REAL_ITEM_ID"}'
```

Both endpoints always return HTTP 200 — both Plex and Jellyfin require this.

## Architecture

```
app/main.py       — Flask app factory (create_app) + Waitress entry point
app/config.py     — Loads YAML config, env vars override; validates at least one backend present
app/labeler.py    — Plex: fetches item by ratingKey, computes diff, calls item.addLabel()
app/jellyfin.py   — Jellyfin: GET /Items/{Id} → merge tags → PUT /Items/{Id} via requests
app/logs.py       — Rotating file handler + stdout stream handler
config/           — Mount point for config.yaml (read-only in Docker)
```

`create_app()` wires everything: load config → init logging → conditionally init PlexServer and/or Jellyfin config → register webhook routes.

## Webhook endpoints

| Path | Backend | Notes |
|---|---|---|
| `POST /webhook/plex` | Plex | multipart/form-data, `payload` JSON field |
| `POST /webhook` | Plex | backward-compat alias |
| `POST /webhook/jellyfin` | Jellyfin | JSON body |
| `GET /healthz` | — | container healthcheck |

With `WEBHOOK_TOKEN=secret`: paths become `/webhook/plex/secret`, `/webhook/secret`, `/webhook/jellyfin/secret`.

## Configuration

Copy `config/config.example.yaml` to `config/config.yaml`. Both backends are optional — remove a section to disable it.

```yaml
labels:
  - auto-labeled

plex:                        # optional
  url: "http://plex.local:32400"
  token: "xxxx"
  library_types: [movie, show]

jellyfin:                    # optional
  url: "http://jellyfin.local:8096"
  api_key: "xxxx"
  item_types: [Movie, Episode, Series]
```

| Env var | Overrides |
|---|---|
| `PLEX_URL` | `plex.url` |
| `PLEX_TOKEN` | `plex.token` |
| `JELLYFIN_URL` | `jellyfin.url` |
| `JELLYFIN_API_KEY` | `jellyfin.api_key` |
| `CONFIG_PATH` | path to YAML (default `/config/config.yaml`) |
| `LOG_LEVEL` | `logging.level` |
| `WEBHOOK_TOKEN` | appends secret to all webhook paths |
| `BIND_HOST` / `BIND_PORT` | listen address (default `0.0.0.0:8080`) |

Never commit `config/config.yaml` — it contains auth tokens.

## Key conventions

- **Always return 200.** Both Plex and Jellyfin don't retry on non-2xx; exceptions are logged and swallowed.
- **Additive merging.** Both backends compute `to_add = [t for t in tags if t not in existing]` and only write when there's something new.
- **Event filtering.** Plex: only `library.new` events; filtered by `librarySectionType`. Jellyfin: only `ItemAdded` notifications; filtered by `ItemType`.
- **Jellyfin tag write is GET → merge → PUT.** The full item body is retrieved, `Tags` is updated in place, and the whole item is PUT back.
- **Entry point:** `python -m app.main` → `main()` → `create_app()` → `waitress.serve()`.
