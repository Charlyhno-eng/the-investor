"""Single independent worker: queued imports first, scheduled refreshes between jobs."""

import logging
import time

from investor import db
from investor.ingest import fred, world_bank
from investor.market import CRYPTO, import_symbol, process_one

log = logging.getLogger(__name__)


def main():
    logging.basicConfig(level=logging.INFO)
    scheduled = []
    next_refresh = 0.0
    while True:
        try:
            if process_one():
                continue
            if not scheduled and time.monotonic() >= next_refresh:
                with db.connect() as connection:
                    imported = [
                        (row["id"][3:].upper(), row["category"])
                        for row in connection.execute(
                            "SELECT id,category FROM assets WHERE source='yahoo'"
                        )
                    ]
                symbols = {s: "crypto" for s in CRYPTO}
                symbols.update(dict(imported))
                scheduled = [world_bank, fred] + [
                    lambda s=s, c=c: import_symbol(s, c) for s, c in symbols.items()
                ]
                next_refresh = time.monotonic() + 86400
            if scheduled:
                task = scheduled.pop(0)
                try:
                    task()
                except Exception:
                    log.exception(
                        "Actualisation incomplète ; données précédentes conservées"
                    )
            else:
                time.sleep(2)
        except KeyboardInterrupt:
            return
        except Exception:
            log.exception("Erreur du worker")
            time.sleep(2)


if __name__ == "__main__":
    main()
