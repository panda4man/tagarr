# Config env-var coverage

## Goal

Make `config/config.yaml` untouchable in normal operation. Every YAML knob gets a corresponding env-var override so deployments are driven entirely by env (e.g., `.env` next to `docker-compose.yml`). YAML remains as fallback for odd cases.

## Current state

`app/config.py` already supports env overrides for:

- `PLEX_URL`, `PLEX_TOKEN`
- `JELLYFIN_URL`, `JELLYFIN_API_KEY`
- `LOG_LEVEL`
- `WEBHOOK_TOKEN`
- `CONFIG_PATH`, `BIND_HOST`, `BIND_PORT`

YAML-only knobs (gap):

- `labels` (list of strings)
- `plex.library_types` (list of strings)
- `jellyfin.item_types` (list of strings)
- `logging.file` (string)
- `logging.max_bytes` (int)
- `logging.backup_count` (int)

## New env vars

| Var | Type | Parsed as | Default (if no env, no YAML) |
| --- | ---- | --------- | ---------------------------- |
| `LABELS` | JSON array of strings | `json.loads` → `list[str]` | none — startup error if neither env nor YAML provides it |
| `PLEX_LIBRARY_TYPES` | JSON array of strings | `json.loads` → `list[str]` | `["movie","show"]` |
| `JELLYFIN_ITEM_TYPES` | JSON array of strings | `json.loads` → `list[str]` | `["Movie","Episode","Series"]` |
| `LOG_FILE` | string | as-is | `/var/log/tagarr/app.log` |
| `LOG_MAX_BYTES` | int | `int(...)` | `5242880` |
| `LOG_BACKUP_COUNT` | int | `int(...)` | `5` |

## Precedence

Existing pattern preserved: **env var > YAML value > built-in default**.

## Parsing rules

- JSON-array envs: parse with `json.loads`; result must be `list` of `str`, otherwise raise `ValueError("<VAR> must be a JSON array of strings")`.
- Int envs: parse with `int(...)`; raise `ValueError("<VAR> must be an integer")` on failure.
- Empty string env → treat as unset (skip override).

## Affected files

- `app/config.py` — extend env-override pattern to the six new knobs.
- `tests/` — new tests for env override behavior (JSON list parse, int parse, precedence, error cases).
- `docker-compose.yml` — add commented examples for new env vars.
- `README.md` — expand env-var table.
- `config/config.example.yaml` — comment noting all keys are optional when env vars set.
- `config/config.yaml` — left alone (user's local file).

## Non-goals

- Removing YAML support.
- Adding env vars for things not already in YAML.
- Restructuring `AppConfig` dataclasses.
