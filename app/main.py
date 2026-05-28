import json
import logging
import os
import sys

from flask import Flask, request
from plexapi.server import PlexServer
from waitress import serve

from app.config import load_config
from app.jellyfin import apply_tags as jellyfin_apply_tags
from app.labeler import apply_labels
from app.logs import setup_logging

log = logging.getLogger("plex-labeling")


def create_app():
    cfg = load_config()
    setup_logging(
        level=cfg.logging.level,
        file_path=cfg.logging.file,
        max_bytes=cfg.logging.max_bytes,
        backup_count=cfg.logging.backup_count,
    )
    log.info("config loaded: labels=%s", cfg.labels)

    plex = None
    if cfg.plex:
        plex = PlexServer(cfg.plex.url, cfg.plex.token)
        log.info(
            "connected to Plex: %s  library_types=%s",
            getattr(plex, "friendlyName", "?"),
            cfg.plex.library_types,
        )

    if cfg.jellyfin:
        log.info(
            "Jellyfin backend configured: url=%s  item_types=%s",
            cfg.jellyfin.url,
            cfg.jellyfin.item_types,
        )

    app = Flask(__name__)

    token_suffix = f"/{cfg.webhook_token}" if cfg.webhook_token else ""
    if cfg.webhook_token:
        log.info("webhook token guard enabled; paths require shared secret")

    # ------------------------------------------------------------------
    # Plex webhook
    # ------------------------------------------------------------------
    def handle_plex_webhook():
        raw_payload = request.form.get("payload")
        if not raw_payload:
            log.warning("plex webhook hit with no payload field")
            return ("", 200)

        try:
            payload = json.loads(raw_payload)
        except json.JSONDecodeError as e:
            log.warning("plex webhook payload not valid JSON: %s", e)
            return ("", 200)

        event = payload.get("event")
        metadata = payload.get("Metadata") or {}
        section_type = metadata.get("librarySectionType")
        rating_key = metadata.get("ratingKey")

        if event != "library.new":
            log.debug("plex: ignoring event=%s", event)
            return ("", 200)

        if section_type not in cfg.plex.library_types:
            log.debug(
                "plex: ignoring library.new for librarySectionType=%s (not in %s)",
                section_type,
                cfg.plex.library_types,
            )
            return ("", 200)

        if not rating_key:
            log.warning("plex: library.new without ratingKey: %s", metadata)
            return ("", 200)

        try:
            apply_labels(plex, int(rating_key), cfg.labels)
        except Exception:
            log.exception("plex: failed to apply labels for rating_key=%s", rating_key)

        return ("", 200)

    # ------------------------------------------------------------------
    # Jellyfin webhook
    # ------------------------------------------------------------------
    def handle_jellyfin_webhook():
        try:
            payload = request.get_json(silent=True) or {}
        except Exception:
            payload = {}

        notification_type = payload.get("NotificationType")
        item_id = payload.get("ItemId")
        item_type = payload.get("ItemType")

        if notification_type != "ItemAdded":
            log.debug("jellyfin: ignoring NotificationType=%s", notification_type)
            return ("", 200)

        if item_type not in cfg.jellyfin.item_types:
            log.debug(
                "jellyfin: ignoring ItemAdded for ItemType=%s (not in %s)",
                item_type,
                cfg.jellyfin.item_types,
            )
            return ("", 200)

        if not item_id:
            log.warning("jellyfin: ItemAdded without ItemId: %s", payload)
            return ("", 200)

        try:
            jellyfin_apply_tags(cfg.jellyfin.url, cfg.jellyfin.api_key, item_id, cfg.labels)
        except Exception:
            log.exception("jellyfin: failed to apply tags for item_id=%s", item_id)

        return ("", 200)

    # ------------------------------------------------------------------
    # Healthcheck
    # ------------------------------------------------------------------
    @app.get("/healthz")
    def healthz():
        return ("ok", 200)

    # ------------------------------------------------------------------
    # Register routes
    # ------------------------------------------------------------------
    if cfg.plex:
        plex_path = f"/webhook/plex{token_suffix}"
        app.add_url_rule(plex_path, view_func=handle_plex_webhook, methods=["POST"])
        # backward-compat alias so existing Plex webhook configs keep working
        legacy_path = f"/webhook{token_suffix}"
        app.add_url_rule(legacy_path, view_func=handle_plex_webhook, methods=["POST"])
        log.info("plex webhook listening on %s (also %s)", plex_path, legacy_path)

    if cfg.jellyfin:
        jf_path = f"/webhook/jellyfin{token_suffix}"
        app.add_url_rule(jf_path, view_func=handle_jellyfin_webhook, methods=["POST"])
        log.info("jellyfin webhook listening on %s", jf_path)

    return app, cfg


def main():
    try:
        app, _cfg = create_app()
    except Exception:
        logging.basicConfig(level=logging.INFO)
        logging.getLogger("plex-labeling").exception("startup failed")
        sys.exit(1)

    host = os.environ.get("BIND_HOST", "0.0.0.0")
    port = int(os.environ.get("BIND_PORT", "8080"))
    log.info("listening on %s:%d", host, port)
    serve(app, host=host, port=port)


if __name__ == "__main__":
    main()
