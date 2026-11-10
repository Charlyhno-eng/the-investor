"""Optional extra consumer; the API also refreshes existing market data."""

import logging
from threading import Event

from investor.imports.runner import consume_imports


def main():
    logging.basicConfig(level=logging.INFO)
    try:
        consume_imports(Event(), seed=True)
    except KeyboardInterrupt:
        return


if __name__ == "__main__":
    main()
