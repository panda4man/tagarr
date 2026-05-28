import json
import logging
import os
import sys

from flask import Flask, request
from plexapi.server import PlexServer
from waitress import serve

from app.config import load_config
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
    log.info(
        "config loaded: plex_url=%s labels=%s library_types=%s",
        cfg.plex.url,
        cfg.labels,
        cfg.library_types,
    )

    plex = PlexServer(cfg.plex.url, cfg.plex.token)
    log.info("connected to Plex: %s", getattr(plex, "friendlyName", "?"))

    app = Flask(__name__)

    webhook_paths = ["/webhook"]
    if cfg.webhook_token:
        webhook_paths = [f"/webhook/{cfg.webhook_token}"]
        log.info("webhook token guard enabled; path requires shared secret")

    @app.get("/healthz")
    def healthz():
        return ("ok", 200)

    def handle_webhook():
        raw_payload = request.form.get("payload")
        if not raw_payload:
            log.warning("webhook hit with no payload field")
            return ("", 200)

        try:
            payload = json.loads(raw_payload)
        except json.JSONDecodeError as e:
            log.warning("webhook payload not valid JSON: %s", e)
            return ("", 200)

        event = payload.get("event")
        metadata = payload.get("Metadata") or {}
        section_type = metadata.get("librarySectionType")
        rating_key = metadata.get("ratingKey")

        if event != "library.new":
            log.debug("ignoring event=%s", event)
            return ("", 200)

        if section_type not in cfg.library_types:
            log.debug(
                "ignoring library.new for librarySectionType=%s (not in %s)",
                section_type,
                cfg.library_types,
            )
            return ("", 200)

        if not rating_key:
            log.warning("library.new without ratingKey: %s", metadata)
            return ("", 200)

        try:
            apply_labels(plex, int(rating_key), cfg.labels)
        except Exception:
            log.exception("failed to apply labels for rating_key=%s", rating_key)

        return ("", 200)

    for path in webhook_paths:
        app.add_url_rule(path, view_func=handle_webhook, methods=["POST"])

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
