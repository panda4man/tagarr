import json
from unittest.mock import MagicMock, patch

import pytest

from app.main import create_app

_PLEX_CONFIG = """
labels:
  - auto-labeled
plex:
  url: http://plex.local:32400
  token: testtoken
"""

_JELLYFIN_CONFIG = """
labels:
  - auto-labeled
jellyfin:
  url: http://jellyfin.local:8096
  api_key: testkey
"""

_BOTH_CONFIG = """
labels:
  - auto-labeled
plex:
  url: http://plex.local:32400
  token: testtoken
jellyfin:
  url: http://jellyfin.local:8096
  api_key: testkey
"""

_PLEX_MOVIE_PAYLOAD = json.dumps(
    {"event": "library.new", "Metadata": {"librarySectionType": "movie", "ratingKey": "42"}}
)

_JF_MOVIE_PAYLOAD = json.dumps(
    {"NotificationType": "ItemAdded", "ItemType": "Movie", "ItemId": "abc123", "Name": "The Matrix"}
)


def _build_app(tmp_path, monkeypatch, yaml_content, extra_env=None):
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml_content)
    monkeypatch.setenv("CONFIG_PATH", str(config_path))
    for key, val in (extra_env or {}).items():
        monkeypatch.setenv(key, val)

    with patch("app.main.PlexServer") as mock_plex_cls, patch("app.main.setup_logging"):
        mock_plex_cls.return_value = MagicMock()
        flask_app, _cfg = create_app()

    flask_app.config["TESTING"] = True
    return flask_app


@pytest.fixture
def plex_client(tmp_path, monkeypatch):
    return _build_app(tmp_path, monkeypatch, _PLEX_CONFIG).test_client()


@pytest.fixture
def jf_client(tmp_path, monkeypatch):
    return _build_app(tmp_path, monkeypatch, _JELLYFIN_CONFIG).test_client()


@pytest.fixture
def both_client(tmp_path, monkeypatch):
    return _build_app(tmp_path, monkeypatch, _BOTH_CONFIG).test_client()


# ---------------------------------------------------------------------------
# Healthcheck
# ---------------------------------------------------------------------------


def test_healthz_returns_ok(plex_client):
    resp = plex_client.get("/healthz")
    assert resp.status_code == 200
    assert resp.data == b"ok"


# ---------------------------------------------------------------------------
# Plex webhook — /webhook/plex and backward-compat /webhook
# ---------------------------------------------------------------------------


def test_plex_library_new_calls_apply_labels(plex_client):
    with patch("app.main.apply_labels") as mock_apply:
        resp = plex_client.post("/webhook/plex", data={"payload": _PLEX_MOVIE_PAYLOAD})
    assert resp.status_code == 200
    mock_apply.assert_called_once()
    _, rating_key, labels = mock_apply.call_args[0]
    assert rating_key == 42
    assert labels == ["auto-labeled"]


def test_plex_legacy_path_still_works(plex_client):
    with patch("app.main.apply_labels") as mock_apply:
        resp = plex_client.post("/webhook", data={"payload": _PLEX_MOVIE_PAYLOAD})
    assert resp.status_code == 200
    mock_apply.assert_called_once()


def test_plex_non_matching_section_type_ignored(plex_client):
    payload = json.dumps(
        {"event": "library.new", "Metadata": {"librarySectionType": "artist", "ratingKey": "42"}}
    )
    with patch("app.main.apply_labels") as mock_apply:
        resp = plex_client.post("/webhook/plex", data={"payload": payload})
    assert resp.status_code == 200
    mock_apply.assert_not_called()


def test_plex_non_library_new_event_ignored(plex_client):
    payload = json.dumps(
        {"event": "media.play", "Metadata": {"librarySectionType": "movie", "ratingKey": "42"}}
    )
    with patch("app.main.apply_labels") as mock_apply:
        resp = plex_client.post("/webhook/plex", data={"payload": payload})
    assert resp.status_code == 200
    mock_apply.assert_not_called()


def test_plex_missing_payload_returns_200(plex_client):
    assert plex_client.post("/webhook/plex", data={}).status_code == 200


def test_plex_malformed_json_returns_200(plex_client):
    assert plex_client.post("/webhook/plex", data={"payload": "not-json"}).status_code == 200


def test_plex_missing_rating_key_returns_200(plex_client):
    payload = json.dumps({"event": "library.new", "Metadata": {"librarySectionType": "movie"}})
    with patch("app.main.apply_labels") as mock_apply:
        resp = plex_client.post("/webhook/plex", data={"payload": payload})
    assert resp.status_code == 200
    mock_apply.assert_not_called()


def test_plex_apply_labels_exception_still_returns_200(plex_client):
    with patch("app.main.apply_labels", side_effect=RuntimeError("plex down")):
        assert plex_client.post("/webhook/plex", data={"payload": _PLEX_MOVIE_PAYLOAD}).status_code == 200


# ---------------------------------------------------------------------------
# Jellyfin webhook — /webhook/jellyfin
# ---------------------------------------------------------------------------


def test_jellyfin_item_added_calls_apply_tags(jf_client):
    with patch("app.main.jellyfin_apply_tags") as mock_apply:
        resp = jf_client.post(
            "/webhook/jellyfin",
            data=_JF_MOVIE_PAYLOAD,
            content_type="application/json",
        )
    assert resp.status_code == 200
    mock_apply.assert_called_once()
    _, _, item_id, tags = mock_apply.call_args[0]
    assert item_id == "abc123"
    assert tags == ["auto-labeled"]


def test_jellyfin_non_matching_item_type_ignored(jf_client):
    payload = json.dumps({"NotificationType": "ItemAdded", "ItemType": "Audio", "ItemId": "x"})
    with patch("app.main.jellyfin_apply_tags") as mock_apply:
        resp = jf_client.post("/webhook/jellyfin", data=payload, content_type="application/json")
    assert resp.status_code == 200
    mock_apply.assert_not_called()


def test_jellyfin_non_item_added_event_ignored(jf_client):
    payload = json.dumps({"NotificationType": "PlaybackStart", "ItemType": "Movie", "ItemId": "x"})
    with patch("app.main.jellyfin_apply_tags") as mock_apply:
        resp = jf_client.post("/webhook/jellyfin", data=payload, content_type="application/json")
    assert resp.status_code == 200
    mock_apply.assert_not_called()


def test_jellyfin_missing_item_id_returns_200(jf_client):
    payload = json.dumps({"NotificationType": "ItemAdded", "ItemType": "Movie"})
    with patch("app.main.jellyfin_apply_tags") as mock_apply:
        resp = jf_client.post("/webhook/jellyfin", data=payload, content_type="application/json")
    assert resp.status_code == 200
    mock_apply.assert_not_called()


def test_jellyfin_apply_tags_exception_still_returns_200(jf_client):
    with patch("app.main.jellyfin_apply_tags", side_effect=RuntimeError("jf down")):
        resp = jf_client.post(
            "/webhook/jellyfin", data=_JF_MOVIE_PAYLOAD, content_type="application/json"
        )
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Both backends registered — no route conflicts
# ---------------------------------------------------------------------------


def test_both_backends_independent_paths(both_client):
    with patch("app.main.apply_labels") as mock_plex, \
         patch("app.main.jellyfin_apply_tags") as mock_jf:
        both_client.post("/webhook/plex", data={"payload": _PLEX_MOVIE_PAYLOAD})
        both_client.post("/webhook/jellyfin", data=_JF_MOVIE_PAYLOAD, content_type="application/json")

    mock_plex.assert_called_once()
    mock_jf.assert_called_once()


# ---------------------------------------------------------------------------
# WEBHOOK_TOKEN guard
# ---------------------------------------------------------------------------


def test_webhook_token_changes_plex_path(tmp_path, monkeypatch):
    app = _build_app(tmp_path, monkeypatch, _PLEX_CONFIG, extra_env={"WEBHOOK_TOKEN": "secret"})
    c = app.test_client()

    assert c.post("/webhook/plex", data={"payload": "{}"}).status_code == 404
    assert c.post("/webhook", data={"payload": "{}"}).status_code == 404

    with patch("app.main.apply_labels"):
        resp = c.post("/webhook/plex/secret", data={"payload": json.dumps({"event": "other"})})
    assert resp.status_code == 200


def test_webhook_token_changes_jellyfin_path(tmp_path, monkeypatch):
    app = _build_app(tmp_path, monkeypatch, _JELLYFIN_CONFIG, extra_env={"WEBHOOK_TOKEN": "secret"})
    c = app.test_client()

    assert c.post("/webhook/jellyfin", data="{}", content_type="application/json").status_code == 404

    with patch("app.main.jellyfin_apply_tags"):
        resp = c.post(
            "/webhook/jellyfin/secret",
            data=json.dumps({"NotificationType": "other"}),
            content_type="application/json",
        )
    assert resp.status_code == 200
