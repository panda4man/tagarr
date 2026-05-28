import pytest

from app.config import load_config


def _write_config(tmp_path, content):
    p = tmp_path / "config.yaml"
    p.write_text(content)
    return str(p)


_PLEX_ONLY = """
labels:
  - auto-labeled
plex:
  url: http://plex.local:32400
  token: mytoken
"""

_JELLYFIN_ONLY = """
labels:
  - auto-labeled
jellyfin:
  url: http://jellyfin.local:8096
  api_key: jfkey
"""

_BOTH = """
labels:
  - auto-labeled
plex:
  url: http://plex.local:32400
  token: mytoken
jellyfin:
  url: http://jellyfin.local:8096
  api_key: jfkey
"""


# ---------------------------------------------------------------------------
# Plex backend
# ---------------------------------------------------------------------------


def test_plex_only_config(tmp_path):
    cfg = load_config(_write_config(tmp_path, _PLEX_ONLY))
    assert cfg.plex is not None
    assert cfg.plex.url == "http://plex.local:32400"
    assert cfg.plex.token == "mytoken"
    assert cfg.plex.library_types == ["movie", "show"]
    assert cfg.jellyfin is None


def test_plex_env_vars_override_yaml(tmp_path, monkeypatch):
    path = _write_config(tmp_path, _PLEX_ONLY)
    monkeypatch.setenv("PLEX_URL", "http://env-plex:32400")
    monkeypatch.setenv("PLEX_TOKEN", "env-token")
    cfg = load_config(path)
    assert cfg.plex.url == "http://env-plex:32400"
    assert cfg.plex.token == "env-token"


def test_plex_partial_credentials_raises(tmp_path):
    path = _write_config(tmp_path, "labels: []\nplex:\n  url: http://plex.local:32400\n")
    with pytest.raises(ValueError):
        load_config(path)


# ---------------------------------------------------------------------------
# Jellyfin backend
# ---------------------------------------------------------------------------


def test_jellyfin_only_config(tmp_path):
    cfg = load_config(_write_config(tmp_path, _JELLYFIN_ONLY))
    assert cfg.jellyfin is not None
    assert cfg.jellyfin.url == "http://jellyfin.local:8096"
    assert cfg.jellyfin.api_key == "jfkey"
    assert cfg.jellyfin.item_types == ["Movie", "Episode", "Series"]
    assert cfg.plex is None


def test_jellyfin_env_vars_override_yaml(tmp_path, monkeypatch):
    path = _write_config(tmp_path, _JELLYFIN_ONLY)
    monkeypatch.setenv("JELLYFIN_URL", "http://env-jf:8096")
    monkeypatch.setenv("JELLYFIN_API_KEY", "env-key")
    cfg = load_config(path)
    assert cfg.jellyfin.url == "http://env-jf:8096"
    assert cfg.jellyfin.api_key == "env-key"


def test_jellyfin_partial_credentials_raises(tmp_path):
    path = _write_config(tmp_path, "labels: []\njellyfin:\n  url: http://jf.local:8096\n")
    with pytest.raises(ValueError):
        load_config(path)


# ---------------------------------------------------------------------------
# Dual backend
# ---------------------------------------------------------------------------


def test_both_backends_configured(tmp_path):
    cfg = load_config(_write_config(tmp_path, _BOTH))
    assert cfg.plex is not None
    assert cfg.jellyfin is not None


def test_no_backends_raises(tmp_path):
    path = _write_config(tmp_path, "labels:\n  - auto-labeled\n")
    with pytest.raises(ValueError, match="at least one backend"):
        load_config(path)


# ---------------------------------------------------------------------------
# Shared config
# ---------------------------------------------------------------------------


def test_labels_validated(tmp_path):
    path = _write_config(tmp_path, "plex:\n  url: http://x\n  token: t\nlabels: not-a-list\n")
    with pytest.raises(ValueError, match="labels"):
        load_config(path)


def test_log_level_env_var(tmp_path, monkeypatch):
    path = _write_config(tmp_path, _PLEX_ONLY)
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("WEBHOOK_TOKEN", "secret")
    cfg = load_config(path)
    assert cfg.logging.level == "DEBUG"
    assert cfg.webhook_token == "secret"


def test_logging_defaults_when_absent(tmp_path):
    cfg = load_config(_write_config(tmp_path, _PLEX_ONLY))
    assert cfg.logging.level == "INFO"
    assert cfg.logging.max_bytes == 5 * 1024 * 1024
    assert cfg.logging.backup_count == 5
