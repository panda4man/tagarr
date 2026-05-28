import json
from unittest.mock import MagicMock, patch

import pytest

from app.main import create_app

_CONFIG_YAML = """
plex:
  url: http://plex.local:32400
  token: testtoken
labels:
  - auto-labeled
library_types:
  - movie
  - show
"""

_LIBRARY_NEW_MOVIE = json.dumps(
    {"event": "library.new", "Metadata": {"librarySectionType": "movie", "ratingKey": "42"}}
)


def _build_app(tmp_path, monkeypatch, extra_env=None):
    config_path = tmp_path / "config.yaml"
    config_path.write_text(_CONFIG_YAML)
    monkeypatch.setenv("CONFIG_PATH", str(config_path))
    for key, val in (extra_env or {}).items():
        monkeypatch.setenv(key, val)

    with patch("app.main.PlexServer") as mock_plex_cls, patch("app.main.setup_logging"):
        mock_plex_cls.return_value = MagicMock()
        flask_app, _cfg = create_app()

    flask_app.config["TESTING"] = True
    return flask_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    return _build_app(tmp_path, monkeypatch).test_client()


# ---------------------------------------------------------------------------
# Healthcheck
# ---------------------------------------------------------------------------


def test_healthz_returns_ok(client):
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.data == b"ok"


# ---------------------------------------------------------------------------
# Routing / event filtering
# ---------------------------------------------------------------------------


def test_library_new_matching_section_calls_apply_labels(client):
    with patch("app.main.apply_labels") as mock_apply:
        resp = client.post("/webhook", data={"payload": _LIBRARY_NEW_MOVIE})
    assert resp.status_code == 200
    mock_apply.assert_called_once()
    _, rating_key, labels = mock_apply.call_args[0]
    assert rating_key == 42
    assert labels == ["auto-labeled"]


def test_library_new_non_matching_section_type_ignored(client):
    payload = json.dumps(
        {"event": "library.new", "Metadata": {"librarySectionType": "artist", "ratingKey": "42"}}
    )
    with patch("app.main.apply_labels") as mock_apply:
        resp = client.post("/webhook", data={"payload": payload})
    assert resp.status_code == 200
    mock_apply.assert_not_called()


def test_non_library_new_event_ignored(client):
    payload = json.dumps(
        {"event": "media.play", "Metadata": {"librarySectionType": "movie", "ratingKey": "42"}}
    )
    with patch("app.main.apply_labels") as mock_apply:
        resp = client.post("/webhook", data={"payload": payload})
    assert resp.status_code == 200
    mock_apply.assert_not_called()


# ---------------------------------------------------------------------------
# Bad / missing payload
# ---------------------------------------------------------------------------


def test_missing_payload_field_returns_200(client):
    resp = client.post("/webhook", data={})
    assert resp.status_code == 200


def test_malformed_json_payload_returns_200(client):
    resp = client.post("/webhook", data={"payload": "not-json"})
    assert resp.status_code == 200


def test_missing_rating_key_returns_200_without_apply(client):
    payload = json.dumps(
        {"event": "library.new", "Metadata": {"librarySectionType": "movie"}}
    )
    with patch("app.main.apply_labels") as mock_apply:
        resp = client.post("/webhook", data={"payload": payload})
    assert resp.status_code == 200
    mock_apply.assert_not_called()


# ---------------------------------------------------------------------------
# Exception safety
# ---------------------------------------------------------------------------


def test_apply_labels_exception_still_returns_200(client):
    with patch("app.main.apply_labels", side_effect=RuntimeError("plex down")):
        resp = client.post("/webhook", data={"payload": _LIBRARY_NEW_MOVIE})
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# WEBHOOK_TOKEN guard
# ---------------------------------------------------------------------------


def test_webhook_token_changes_path(tmp_path, monkeypatch):
    app = _build_app(tmp_path, monkeypatch, extra_env={"WEBHOOK_TOKEN": "secret"})
    c = app.test_client()

    # Original path is no longer registered
    resp = c.post("/webhook", data={"payload": "{}"})
    assert resp.status_code == 404

    # Token-guarded path works
    with patch("app.main.apply_labels"):
        resp = c.post("/webhook/secret", data={"payload": json.dumps({"event": "other"})})
    assert resp.status_code == 200
