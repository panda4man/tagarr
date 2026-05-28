import logging

import requests

log = logging.getLogger(__name__)

_HEADERS_BASE = {"Content-Type": "application/json"}


def _auth_headers(api_key: str) -> dict:
    return {**_HEADERS_BASE, "Authorization": f'MediaBrowser Token="{api_key}"'}


def apply_tags(url: str, api_key: str, item_id: str, tags: list[str]) -> None:
    if not tags:
        log.debug("no tags configured, skipping item_id=%s", item_id)
        return

    headers = _auth_headers(api_key)
    base_url = url.rstrip("/")

    resp = requests.get(f"{base_url}/Items/{item_id}", headers=headers, timeout=10)
    resp.raise_for_status()
    item = resp.json()

    existing = set(item.get("Tags") or [])
    to_add = [t for t in tags if t not in existing]
    title = item.get("Name", "?")

    if not to_add:
        log.info(
            "item_id=%s title=%r already has all tags=%s",
            item_id,
            title,
            tags,
        )
        return

    item["Tags"] = sorted(existing | set(tags))
    resp = requests.put(f"{base_url}/Items/{item_id}", headers=headers, json=item, timeout=10)
    resp.raise_for_status()
    log.info(
        "item_id=%s title=%r added tags=%s existing=%s",
        item_id,
        title,
        to_add,
        sorted(existing),
    )
