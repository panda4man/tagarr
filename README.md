# Tadarr

Tiny Flask service that listens for **Plex** and/or **Jellyfin** webhooks and auto-applies a configured list of labels (Plex) or tags (Jellyfin) to newly added Movies and TV. Existing labels/tags are **merged** — never clobbered.

Either backend can be used on its own, or both at the same time.

## Quick start

1. Copy the example config:
   ```bash
   cp config/config.example.yaml config/config.yaml
   ```
2. Edit `config/config.yaml` — keep the `plex:` section, the `jellyfin:` section, or both. Remove whichever you don't use.
3. Put your tokens in a `.env` next to `docker-compose.yml`:
   ```
   PLEX_URL=http://plex.local:32400
   PLEX_TOKEN=xxxxxxxxxxxxxxxxxxxx
   JELLYFIN_URL=http://jellyfin.local:8096
   JELLYFIN_API_KEY=xxxxxxxxxxxxxxxxxxxx
   ```
4. Build and run:
   ```bash
   docker compose up --build -d
   ```
5. Configure webhooks in your media server(s):
   - **Plex:** Settings → Webhooks → Add Webhook → `http://<docker-host>:8080/webhook/plex`
     (the legacy `/webhook` path still works for existing Plex configs)
   - **Jellyfin:** install the Webhook plugin, add a Generic Destination pointing to `http://<docker-host>:8080/webhook/jellyfin`, and enable the **Item Added** notification.

Plex webhooks require a Plex Pass. Jellyfin needs the official Webhook plugin.

## Configuration

`config/config.yaml`:

```yaml
labels:
  - "auto-labeled"
  - "needs-review"

plex:                              # remove this section if not using Plex
  url: "http://plex.local:32400"
  token: "xxxxxxxx"                # PLEX_TOKEN env var overrides
  library_types:                   # only act on these librarySectionType values
    - movie
    - show

jellyfin:                          # remove this section if not using Jellyfin
  url: "http://jellyfin.local:8096"
  api_key: "xxxxxxxx"              # JELLYFIN_API_KEY env var overrides
  item_types:                      # only act on these ItemType values
    - Movie
    - Episode
    - Series

logging:
  level: INFO
  file: /var/log/plex-labeling/app.log
  max_bytes: 5242880               # 5 MiB
  backup_count: 5
```

At least one of `plex:` or `jellyfin:` must be configured (with both `url` and the matching credential). Startup fails otherwise.

Env vars (override config values):

| Var                 | Purpose                                              |
| ------------------- | ---------------------------------------------------- |
| `PLEX_URL`          | Plex server base URL                                 |
| `PLEX_TOKEN`        | Plex auth token                                      |
| `JELLYFIN_URL`      | Jellyfin server base URL                             |
| `JELLYFIN_API_KEY`  | Jellyfin API key                                     |
| `CONFIG_PATH`       | Path to YAML config (default `/config/config.yaml`)  |
| `LOG_LEVEL`         | Override log level                                   |
| `WEBHOOK_TOKEN`     | If set, webhook paths become `/webhook/<backend>/<token>` (and the legacy Plex alias becomes `/webhook/<token>`) |
| `BIND_HOST`         | Listen host (default `0.0.0.0`)                      |
| `BIND_PORT`         | Listen port (default `8080`)                         |

## Endpoints

- `POST /webhook/plex` — Plex webhook receiver (multipart/form-data, `payload` field). Only registered when Plex is configured.
- `POST /webhook` — legacy alias for `/webhook/plex` so existing Plex webhook configs keep working.
- `POST /webhook/jellyfin` — Jellyfin webhook receiver (JSON body from the Webhook plugin's Generic destination). Only registered when Jellyfin is configured.
- `GET /healthz` — container healthcheck.

When `WEBHOOK_TOKEN` is set, every webhook path above gets a `/<token>` suffix.

## How it merges

- **Plex:** uses `python-plexapi` `item.addLabel(to_add)`, which calls `editTags(..., remove=False)`. Existing labels stay; only new ones are appended.
- **Jellyfin:** fetches the item via `GET /Items/{id}`, unions its current `Tags` with the configured labels, and `PUT`s it back. Existing tags stay; only new ones are appended.

## Logs

Rotated by size to `logging.file` (`backup_count` backups kept) and also streamed to stdout so `docker logs plex-labeling` works.

## Smoke tests without the media server adding content

Plex:
```bash
curl -X POST http://localhost:8080/webhook/plex \
  -F 'payload={"event":"library.new","Metadata":{"librarySectionType":"movie","ratingKey":"REAL_RATING_KEY"}}'
```

Jellyfin:
```bash
curl -X POST http://localhost:8080/webhook/jellyfin \
  -H 'Content-Type: application/json' \
  -d '{"NotificationType":"ItemAdded","ItemType":"Movie","ItemId":"REAL_ITEM_ID"}'
```

Use a real `ratingKey` / `ItemId` from your library, then check the item in the corresponding UI.
