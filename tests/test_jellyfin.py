from unittest.mock import MagicMock, patch

import pytest

from app.jellyfin import apply_tags

_URL = "http://jellyfin.local:8096"
_KEY = "testkey"
_ITEM_ID = "abc123"


def _mock_item(tags=None):
    return {"Id": _ITEM_ID, "Name": "Test Movie", "Tags": list(tags or [])}


def _mock_responses(get_item):
    get_resp = MagicMock()
    get_resp.json.return_value = get_item
    get_resp.raise_for_status = MagicMock()

    put_resp = MagicMock()
    put_resp.raise_for_status = MagicMock()

    return get_resp, put_resp


def test_all_tags_added_when_item_has_none():
    get_resp, put_resp = _mock_responses(_mock_item(tags=[]))
    with patch("app.jellyfin.requests.get", return_value=get_resp) as mock_get, \
         patch("app.jellyfin.requests.put", return_value=put_resp) as mock_put:
        apply_tags(_URL, _KEY, _ITEM_ID, ["auto-labeled", "needs-review"])

    mock_get.assert_called_once()
    mock_put.assert_called_once()
    put_body = mock_put.call_args.kwargs["json"]
    assert set(put_body["Tags"]) == {"auto-labeled", "needs-review"}


def test_no_op_when_item_already_has_all_tags():
    get_resp, put_resp = _mock_responses(_mock_item(tags=["auto-labeled", "needs-review"]))
    with patch("app.jellyfin.requests.get", return_value=get_resp), \
         patch("app.jellyfin.requests.put", return_value=put_resp) as mock_put:
        apply_tags(_URL, _KEY, _ITEM_ID, ["auto-labeled", "needs-review"])

    mock_put.assert_not_called()


def test_partial_overlap_adds_only_missing_tags():
    get_resp, put_resp = _mock_responses(_mock_item(tags=["auto-labeled"]))
    with patch("app.jellyfin.requests.get", return_value=get_resp), \
         patch("app.jellyfin.requests.put", return_value=put_resp) as mock_put:
        apply_tags(_URL, _KEY, _ITEM_ID, ["auto-labeled", "needs-review"])

    mock_put.assert_called_once()
    put_body = mock_put.call_args.kwargs["json"]
    assert "needs-review" in put_body["Tags"]
    assert "auto-labeled" in put_body["Tags"]


def test_empty_tags_list_skips_without_get():
    with patch("app.jellyfin.requests.get") as mock_get:
        apply_tags(_URL, _KEY, _ITEM_ID, [])
    mock_get.assert_not_called()


def test_trailing_slash_stripped_from_url():
    get_resp, put_resp = _mock_responses(_mock_item())
    with patch("app.jellyfin.requests.get", return_value=get_resp) as mock_get, \
         patch("app.jellyfin.requests.put", return_value=put_resp):
        apply_tags(_URL + "/", _KEY, _ITEM_ID, ["auto-labeled"])

    called_url = mock_get.call_args.args[0]
    assert "//" not in called_url.replace("http://", "")
