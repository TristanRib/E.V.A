"""Point d'entrée : `python -m eva` ou `eva`."""

import asyncio
import contextlib

from eva import app


def main() -> None:
    with contextlib.suppress(KeyboardInterrupt):  # Ctrl+C en attente de saisie : quitter
        asyncio.run(app.run())


if __name__ == "__main__":
    main()
