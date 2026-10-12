"""Import FreeMoCap 1.8.2 safely, whatever logging is already configured.

Importing it while the root logger has handlers fails with a circular
import; importing it with none installs a TRACE console handler and a log
file. So the import runs with no root handlers, and afterwards the root
logger gets back exactly the handlers and level it had.
"""

import logging
import sys


def import_freemocap() -> None:
    if "freemocap" in sys.modules:
        return
    root = logging.getLogger()
    handlers, level = root.handlers[:], root.level
    root.handlers = []
    try:
        import freemocap  # noqa: F401
    finally:
        root.handlers = handlers
        root.setLevel(level)
