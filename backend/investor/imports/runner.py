"""Refresh local data and consume the durable queue in the background."""

import logging
from threading import Event
from time import monotonic

from investor.imports.refresh import schedule_refreshes
from investor.imports.service import process_one

log = logging.getLogger(__name__)


def consume_imports(stop: Event, *, seed=False):
    next_check = 0.0
    while not stop.is_set():
        try:
            if monotonic() >= next_check:
                schedule_refreshes(seed=seed)
                next_check = monotonic() + 30
            if process_one():
                continue
        except Exception:
            log.exception("Erreur de la file d’import")
        stop.wait(0.5)
