import logging

from plexapi.server import PlexServer

log = logging.getLogger(__name__)


def apply_labels(plex: PlexServer, rating_key: int, labels: list[str]) -> None:
    if not labels:
        log.debug("no labels configured, skipping rating_key=%s", rating_key)
        return

    item = plex.fetchItem(int(rating_key))
    existing = {l.tag for l in (getattr(item, "labels", None) or [])}
    to_add = [l for l in labels if l not in existing]

    title = getattr(item, "title", "?")
    if not to_add:
        log.info(
            "rating_key=%s title=%r already has all labels=%s",
            rating_key,
            title,
            labels,
        )
        return

    item.addLabel(to_add)
    log.info(
        "rating_key=%s title=%r added labels=%s existing=%s",
        rating_key,
        title,
        to_add,
        sorted(existing),
    )
