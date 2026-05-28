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
    file: str = "/var/log/plex-labeling/app.log"
    max_bytes: int = 5 * 1024 * 1024
    backup_count: int = 5


@dataclass
class AppConfig:
    labels: list[str]
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    webhook_token: str | None = None
    plex: PlexConfig | None = None
    jellyfin: JellyfinConfig | None = None


def load_config(path: str | None = None) -> AppConfig:
    path = path or os.environ.get("CONFIG_PATH", "/config/config.yaml")
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    labels = raw.get("labels") or []
    if not isinstance(labels, list) or not all(isinstance(x, str) for x in labels):
        raise ValueError("labels must be a list of strings")

    log_raw = raw.get("logging", {}) or {}
    logging_cfg = LoggingConfig(
        level=os.environ.get("LOG_LEVEL") or log_raw.get("level", "INFO"),
        file=log_raw.get("file", "/var/log/plex-labeling/app.log"),
        max_bytes=int(log_raw.get("max_bytes", 5 * 1024 * 1024)),
        backup_count=int(log_raw.get("backup_count", 5)),
    )

    plex_cfg = None
    plex_raw = raw.get("plex", {}) or {}
    plex_url = os.environ.get("PLEX_URL") or plex_raw.get("url")
    plex_token = os.environ.get("PLEX_TOKEN") or plex_raw.get("token")
    if plex_url and plex_token:
        library_types = plex_raw.get("library_types") or ["movie", "show"]
        if not isinstance(library_types, list):
            raise ValueError("plex.library_types must be a list")
        plex_cfg = PlexConfig(url=plex_url, token=plex_token, library_types=library_types)
    elif plex_url or plex_token:
        raise ValueError("plex config requires both url and token")

    jellyfin_cfg = None
    jf_raw = raw.get("jellyfin", {}) or {}
    jf_url = os.environ.get("JELLYFIN_URL") or jf_raw.get("url")
    jf_api_key = os.environ.get("JELLYFIN_API_KEY") or jf_raw.get("api_key")
    if jf_url and jf_api_key:
        item_types = jf_raw.get("item_types") or ["Movie", "Episode", "Series"]
        if not isinstance(item_types, list):
            raise ValueError("jellyfin.item_types must be a list")
        jellyfin_cfg = JellyfinConfig(url=jf_url, api_key=jf_api_key, item_types=item_types)
    elif jf_url or jf_api_key:
        raise ValueError("jellyfin config requires both url and api_key")

    if plex_cfg is None and jellyfin_cfg is None:
        raise ValueError("at least one backend (plex or jellyfin) must be configured")

    return AppConfig(
        labels=labels,
        logging=logging_cfg,
        webhook_token=os.environ.get("WEBHOOK_TOKEN"),
        plex=plex_cfg,
        jellyfin=jellyfin_cfg,
    )
