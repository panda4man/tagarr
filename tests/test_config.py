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


# ---------------------------------------------------------------------------
# Env-var overrides for list/int knobs
# ---------------------------------------------------------------------------


def test_labels_env_var_overrides_yaml(tmp_path, monkeypatch):
    path = _write_config(tmp_path, _PLEX_ONLY)
    monkeypatch.setenv("LABELS", '["from-env", "second"]')
    cfg = load_config(path)
    assert cfg.labels == ["from-env", "second"]


def test_labels_env_var_without_yaml_section(tmp_path, monkeypatch):
    path = _write_config(tmp_path, "plex:\n  url: http://x\n  token: t\n")
    monkeypatch.setenv("LABELS", '["only-from-env"]')
    cfg = load_config(path)
    assert cfg.labels == ["only-from-env"]


def test_labels_env_var_invalid_json_raises(tmp_path, monkeypatch):
    path = _write_config(tmp_path, _PLEX_ONLY)
    monkeypatch.setenv("LABELS", "not-json")
    with pytest.raises(ValueError, match="LABELS"):
        load_config(path)


def test_labels_env_var_not_array_raises(tmp_path, monkeypatch):
    path = _write_config(tmp_path, _PLEX_ONLY)
    monkeypatch.setenv("LABELS", '"a-string"')
    with pytest.raises(ValueError, match="LABELS"):
        load_config(path)


def test_labels_env_var_not_strings_raises(tmp_path, monkeypatch):
    path = _write_config(tmp_path, _PLEX_ONLY)
    monkeypatch.setenv("LABELS", "[1, 2, 3]")
    with pytest.raises(ValueError, match="LABELS"):
        load_config(path)


def test_plex_library_types_env_var_overrides_yaml(tmp_path, monkeypatch):
    path = _write_config(tmp_path, _PLEX_ONLY)
    monkeypatch.setenv("PLEX_LIBRARY_TYPES", '["movie"]')
    cfg = load_config(path)
    assert cfg.plex.library_types == ["movie"]


def test_plex_library_types_env_var_invalid_raises(tmp_path, monkeypatch):
    path = _write_config(tmp_path, _PLEX_ONLY)
    monkeypatch.setenv("PLEX_LIBRARY_TYPES", "not-json")
    with pytest.raises(ValueError, match="PLEX_LIBRARY_TYPES"):
        load_config(path)


def test_jellyfin_item_types_env_var_overrides_yaml(tmp_path, monkeypatch):
    path = _write_config(tmp_path, _JELLYFIN_ONLY)
    monkeypatch.setenv("JELLYFIN_ITEM_TYPES", '["Movie"]')
    cfg = load_config(path)
    assert cfg.jellyfin.item_types == ["Movie"]


def test_jellyfin_item_types_env_var_invalid_raises(tmp_path, monkeypatch):
    path = _write_config(tmp_path, _JELLYFIN_ONLY)
    monkeypatch.setenv("JELLYFIN_ITEM_TYPES", "[1]")
    with pytest.raises(ValueError, match="JELLYFIN_ITEM_TYPES"):
        load_config(path)


def test_log_file_env_var_overrides_yaml(tmp_path, monkeypatch):
    path = _write_config(tmp_path, _PLEX_ONLY)
    monkeypatch.setenv("LOG_FILE", "/tmp/env-app.log")
    cfg = load_config(path)
    assert cfg.logging.file == "/tmp/env-app.log"


def test_log_max_bytes_env_var_overrides_yaml(tmp_path, monkeypatch):
    path = _write_config(tmp_path, _PLEX_ONLY)
    monkeypatch.setenv("LOG_MAX_BYTES", "1048576")
    cfg = load_config(path)
    assert cfg.logging.max_bytes == 1048576


def test_log_max_bytes_env_var_invalid_raises(tmp_path, monkeypatch):
    path = _write_config(tmp_path, _PLEX_ONLY)
    monkeypatch.setenv("LOG_MAX_BYTES", "not-int")
    with pytest.raises(ValueError, match="LOG_MAX_BYTES"):
        load_config(path)


def test_log_backup_count_env_var_overrides_yaml(tmp_path, monkeypatch):
    path = _write_config(tmp_path, _PLEX_ONLY)
    monkeypatch.setenv("LOG_BACKUP_COUNT", "9")
    cfg = load_config(path)
    assert cfg.logging.backup_count == 9


def test_log_backup_count_env_var_invalid_raises(tmp_path, monkeypatch):
    path = _write_config(tmp_path, _PLEX_ONLY)
    monkeypatch.setenv("LOG_BACKUP_COUNT", "not-int")
    with pytest.raises(ValueError, match="LOG_BACKUP_COUNT"):
        load_config(path)


def test_missing_labels_raises(tmp_path):
    path = _write_config(tmp_path, "plex:\n  url: http://x\n  token: t\n")
    with pytest.raises(ValueError, match="labels"):
        load_config(path)


def test_empty_env_var_treated_as_unset(tmp_path, monkeypatch):
    path = _write_config(tmp_path, _PLEX_ONLY)
    monkeypatch.setenv("LABELS", "")
    monkeypatch.setenv("LOG_MAX_BYTES", "")
    cfg = load_config(path)
    assert cfg.labels == ["auto-labeled"]
    assert cfg.logging.max_bytes == 5 * 1024 * 1024
