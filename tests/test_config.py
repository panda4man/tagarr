import pytest

from app.config import load_config


def _write_config(tmp_path, content):
    p = tmp_path / "config.yaml"
    p.write_text(content)
    return str(p)


_MINIMAL = """
plex:
  url: http://plex.local:32400
  token: mytoken
labels:
  - auto-labeled
"""


def test_minimal_valid_config(tmp_path):
    cfg = load_config(_write_config(tmp_path, _MINIMAL))
    assert cfg.plex.url == "http://plex.local:32400"
    assert cfg.plex.token == "mytoken"
    assert cfg.labels == ["auto-labeled"]
    assert cfg.library_types == ["movie", "show"]


def test_env_vars_override_yaml(tmp_path, monkeypatch):
    path = _write_config(tmp_path, _MINIMAL)
    monkeypatch.setenv("PLEX_URL", "http://env-plex:32400")
    monkeypatch.setenv("PLEX_TOKEN", "env-token")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("WEBHOOK_TOKEN", "secret")

    cfg = load_config(path)

    assert cfg.plex.url == "http://env-plex:32400"
    assert cfg.plex.token == "env-token"
    assert cfg.logging.level == "DEBUG"
    assert cfg.webhook_token == "secret"


def test_missing_url_raises(tmp_path):
    path = _write_config(tmp_path, "plex:\n  token: mytoken\nlabels: []\n")
    with pytest.raises(ValueError):
        load_config(path)


def test_missing_token_raises(tmp_path):
    path = _write_config(tmp_path, "plex:\n  url: http://plex.local:32400\nlabels: []\n")
    with pytest.raises(ValueError):
        load_config(path)


def test_invalid_labels_raises(tmp_path):
    path = _write_config(
        tmp_path,
        "plex:\n  url: http://x:32400\n  token: t\nlabels: not-a-list\n",
    )
    with pytest.raises(ValueError, match="labels"):
        load_config(path)


def test_library_types_defaults_when_absent(tmp_path):
    path = _write_config(tmp_path, "plex:\n  url: http://x:32400\n  token: t\nlabels: []\n")
    cfg = load_config(path)
    assert cfg.library_types == ["movie", "show"]


def test_logging_defaults_when_absent(tmp_path):
    path = _write_config(tmp_path, "plex:\n  url: http://x:32400\n  token: t\nlabels: []\n")
    cfg = load_config(path)
    assert cfg.logging.level == "INFO"
    assert cfg.logging.max_bytes == 5 * 1024 * 1024
    assert cfg.logging.backup_count == 5
