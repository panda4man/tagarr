import json
import os
from dataclasses import dataclass, field

import yaml


@dataclass
class PlexConfig:
    url: str
    token: str
    library_types: list[str] = field(default_factory=lambda: ["movie", "show"])


@dataclass
class JellyfinConfig:
    url: str
    api_key: str
    item_types: list[str] = field(default_factory=lambda: ["Movie", "Episode", "Series"])


@dataclass
class LoggingConfig:
    level: str = "INFO"
    file: str = "/var/log/tagarr/app.log"
    max_bytes: int = 5 * 1024 * 1024
    backup_count: int = 5


@dataclass
class AppConfig:
    labels: list[str]
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    webhook_token: str | None = None
    plex: PlexConfig | None = None
    jellyfin: JellyfinConfig | None = None


def _env(name: str) -> str | None:
    val = os.environ.get(name)
    if val is None or val == "":
        return None
    return val


def _env_str_list(name: str) -> list[str] | None:
    raw = _env(name)
    if raw is None:
        return None
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{name} must be a JSON array of strings") from exc
    if not isinstance(parsed, list) or not all(isinstance(x, str) for x in parsed):
        raise ValueError(f"{name} must be a JSON array of strings")
    return parsed


def _resolve_int(env_name: str, yaml_value, default: int) -> int:
    raw = _env(env_name)
    if raw is not None:
        try:
            return int(raw)
        except ValueError as exc:
            raise ValueError(f"{env_name} must be an integer") from exc
    if yaml_value is not None:
        return int(yaml_value)
    return default


def _resolve_str_list(env_name: str, yaml_value, default: list[str] | None) -> list[str] | None:
    from_env = _env_str_list(env_name)
    if from_env is not None:
        return from_env
    if yaml_value is not None:
        if not isinstance(yaml_value, list) or not all(isinstance(x, str) for x in yaml_value):
            raise ValueError(f"{env_name.lower()} must be a list of strings")
        return yaml_value
    return default


def load_config(path: str | None = None) -> AppConfig:
    path = path or os.environ.get("CONFIG_PATH", "/config/config.yaml")
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    labels = _resolve_str_list("LABELS", raw.get("labels"), default=None)
    if labels is None:
        raise ValueError("labels must be set via YAML or LABELS env var")

    log_raw = raw.get("logging", {}) or {}
    logging_cfg = LoggingConfig(
        level=_env("LOG_LEVEL") or log_raw.get("level", "INFO"),
        file=_env("LOG_FILE") or log_raw.get("file", "/var/log/tagarr/app.log"),
        max_bytes=_resolve_int("LOG_MAX_BYTES", log_raw.get("max_bytes"), 5 * 1024 * 1024),
        backup_count=_resolve_int("LOG_BACKUP_COUNT", log_raw.get("backup_count"), 5),
    )

    plex_cfg = None
    plex_raw = raw.get("plex", {}) or {}
    plex_url = _env("PLEX_URL") or plex_raw.get("url")
    plex_token = _env("PLEX_TOKEN") or plex_raw.get("token")
    if plex_url and plex_token:
        library_types = _resolve_str_list(
            "PLEX_LIBRARY_TYPES",
            plex_raw.get("library_types"),
            default=["movie", "show"],
        )
        plex_cfg = PlexConfig(url=plex_url, token=plex_token, library_types=library_types)
    elif plex_url or plex_token:
        raise ValueError("plex config requires both url and token")

    jellyfin_cfg = None
    jf_raw = raw.get("jellyfin", {}) or {}
    jf_url = _env("JELLYFIN_URL") or jf_raw.get("url")
    jf_api_key = _env("JELLYFIN_API_KEY") or jf_raw.get("api_key")
    if jf_url and jf_api_key:
        item_types = _resolve_str_list(
            "JELLYFIN_ITEM_TYPES",
            jf_raw.get("item_types"),
            default=["Movie", "Episode", "Series"],
        )
        jellyfin_cfg = JellyfinConfig(url=jf_url, api_key=jf_api_key, item_types=item_types)
    elif jf_url or jf_api_key:
        raise ValueError("jellyfin config requires both url and api_key")

    if plex_cfg is None and jellyfin_cfg is None:
        raise ValueError("at least one backend (plex or jellyfin) must be configured")

    return AppConfig(
        labels=labels,
        logging=logging_cfg,
        webhook_token=_env("WEBHOOK_TOKEN"),
        plex=plex_cfg,
        jellyfin=jellyfin_cfg,
    )
