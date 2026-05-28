from unittest.mock import MagicMock

from app.labeler import apply_labels


def _make_plex(label_tags=None):
    item = MagicMock()
    item.labels = [MagicMock(tag=t) for t in (label_tags or [])]
    item.title = "Test Movie"
    plex = MagicMock()
    plex.fetchItem.return_value = item
    return plex, item


def test_all_labels_added_when_item_has_none():
    plex, item = _make_plex(label_tags=[])
    apply_labels(plex, 123, ["auto-labeled", "needs-review"])
    item.addLabel.assert_called_once_with(["auto-labeled", "needs-review"])


def test_no_op_when_item_already_has_all_labels():
    plex, item = _make_plex(label_tags=["auto-labeled", "needs-review"])
    apply_labels(plex, 123, ["auto-labeled", "needs-review"])
    item.addLabel.assert_not_called()


def test_partial_overlap_adds_only_missing_labels():
    plex, item = _make_plex(label_tags=["auto-labeled"])
    apply_labels(plex, 123, ["auto-labeled", "needs-review"])
    item.addLabel.assert_called_once_with(["needs-review"])


def test_empty_labels_list_skips_fetch_and_add():
    plex = MagicMock()
    apply_labels(plex, 123, [])
    plex.fetchItem.assert_not_called()
