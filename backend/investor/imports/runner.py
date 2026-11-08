"""Consume the durable import queue even when the bulk refresh worker is stopped."""

import logging
from threading import Event

from investor.imports.service import process_one

log = logging.getLogger(__name__)


def consume_imports(stop: Event):
    while not stop.is_set():
        try:
            if process_one():
                continue
        except Exception:
            log.exception("Erreur de la file d’import")
        stop.wait(0.5)
