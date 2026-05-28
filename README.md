# Tadarr 

Tiny Flask service that listens for Plex Pass webhooks and auto-applies a configured list of labels to newly added Movies and TV Shows. Labels are **merged** with existing labels — never clobbered.

## Quick start

1. Copy the example config:
   ```bash
   cp config/config.example.yaml config/config.yaml
   ```
2. Edit `config/config.yaml` (or use env vars) to set your Plex URL, token, and label list.
3. Put your Plex token in a `.env` next to `docker-compose.yml`:
   ```
   PLEX_URL=http://plex.local:32400
   PLEX_TOKEN=xxxxxxxxxxxxxxxxxxxx
   ```
4. Build and run:
   ```bash
   docker compose up --build -d
   ```
5. In Plex: **Settings → Webhooks → Add Webhook** → `http://<docker-host>:8080/webhook`

Plex webhooks require a Plex Pass.

## Configuration

`config/config.yaml`:

```yaml
plex:
  url: "http://plex.local:32400"
  token: "xxxxxxxx"          # PLEX_TOKEN env var overrides

labels:
  - "auto-labeled"
  - "needs-review"

library_types:               # only act on these librarySectionType values
  - movie
  - show

logging:
  level: INFO
  file: /var/log/plex-labeling/app.log
  max_bytes: 5242880         # 5 MiB
  backup_count: 5
```

Env vars (override config values):

| Var             | Purpose                                          |
| --------------- | ------------------------------------------------ |
| `PLEX_URL`      | Plex server base URL                             |
| `PLEX_TOKEN`    | Plex auth token                                  |
| `CONFIG_PATH`   | Path to YAML config (default `/config/config.yaml`) |
| `LOG_LEVEL`     | Override log level                               |
| `WEBHOOK_TOKEN` | If set, webhook path becomes `/webhook/<token>` |
| `BIND_HOST`     | Listen host (default `0.0.0.0`)                  |
| `BIND_PORT`     | Listen port (default `8080`)                     |

## Endpoints

- `POST /webhook` — Plex webhook receiver (multipart/form-data, `payload` field).
- `GET /healthz` — container healthcheck.

## How it merges

Uses `python-plexapi` `item.addLabel(to_add)`, which calls `editTags(..., remove=False)`. Existing labels stay; only new ones are appended.

## Logs

Rotated by size to `logging.file` (`backup_count` backups kept) and also streamed to stdout so `docker logs plex-labeling` works.

## Smoke test without Plex adding content

```bash
curl -X POST http://localhost:8080/webhook \
  -F 'payload={"event":"library.new","Metadata":{"librarySectionType":"movie","ratingKey":"REAL_RATING_KEY"}}'
```

Use a real `ratingKey` from your library, then check the item in the Plex UI.
