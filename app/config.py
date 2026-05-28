import os
from dataclasses import dataclass, field

import yaml


@dataclass
class PlexConfig:
    url: str
    token: str


@dataclass
class LoggingConfig:
    level: str = "INFO"
    file: str = "/var/log/plex-labeling/app.log"
    max_bytes: int = 5 * 1024 * 1024
    backup_count: int = 5


@dataclass
class AppConfig:
    plex: PlexConfig
    labels: list[str]
    library_types: list[str]
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    webhook_token: str | None = None


def load_config(path: str | None = None) -> AppConfig:
    path = path or os.environ.get("CONFIG_PATH", "/config/config.yaml")
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    plex_raw = raw.get("plex", {}) or {}
    url = os.environ.get("PLEX_URL") or plex_raw.get("url")
    token = os.environ.get("PLEX_TOKEN") or plex_raw.get("token")
    if not url or not token:
        raise ValueError("plex.url and plex.token must be set (config or env)")

    log_raw = raw.get("logging", {}) or {}
    logging_cfg = LoggingConfig(
        level=os.environ.get("LOG_LEVEL") or log_raw.get("level", "INFO"),
        file=log_raw.get("file", "/var/log/plex-labeling/app.log"),
        max_bytes=int(log_raw.get("max_bytes", 5 * 1024 * 1024)),
        backup_count=int(log_raw.get("backup_count", 5)),
    )

    labels = raw.get("labels") or []
    if not isinstance(labels, list) or not all(isinstance(x, str) for x in labels):
        raise ValueError("labels must be a list of strings")

    library_types = raw.get("library_types") or ["movie", "show"]
    if not isinstance(library_types, list):
        raise ValueError("library_types must be a list")

    return AppConfig(
        plex=PlexConfig(url=url, token=token),
        labels=labels,
        library_types=library_types,
        logging=logging_cfg,
        webhook_token=os.environ.get("WEBHOOK_TOKEN"),
    )
