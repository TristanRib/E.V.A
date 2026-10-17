"""Interface de discussion en terminal."""

import asyncio
import contextlib
import signal
import sys
import threading
from collections.abc import Iterator
from typing import Any

from eva.application import Agent, AgentEvent, TextDelta
from eva.domain import EvaError

_HELP = "Commandes : /reset (nouvelle conversation), /quit (quitter)"


class CliInterface:
    def __init__(self, agent: Agent, *, title: str) -> None:
        self._agent = agent
        self._title = title

    async def run(self) -> None:
        print(f"E.V.A en ligne — {self._title}")
        print(_HELP, end="\n\n")
        lines = _StdinLines()

        while True:
            print("Vous › ", end="", flush=True)
            text = await lines.next()
            if text is None:  # fin de l'entrée (Ctrl+Z / Ctrl+D, ou entrée redirigée)
                print()
                break
            text = text.strip()
            if not text:
                continue
            if text in {"/quit", "/exit"}:
                break
            if text == "/reset":
                self._agent.conversation.clear()
                print("— Nouvelle conversation —\n")
                continue
            await self._turn(text)

        print("À bientôt.")

    async def _turn(self, text: str) -> None:
        print("EVA › ", end="", flush=True)
        task = asyncio.create_task(self._agent.ask(text, sink=self))
        with _cancel_on_ctrl_c(task):
            try:
                await task
            except asyncio.CancelledError:
                current = asyncio.current_task()
                if current is not None and current.cancelling():
                    raise  # arrêt de l'application, pas seulement du tour
                print("\n[interrompu]\n")
                return
            except EvaError as e:
                print(f"\n[erreur] {e}\n")
                return
        print("\n")

    def emit(self, event: AgentEvent) -> None:
        if isinstance(event, TextDelta):
            print(event.text, end="", flush=True)


class _StdinLines:
    """Lit l'entrée standard dans un thread démon, sans bloquer la boucle asyncio.

    Un thread démon ne retient pas la fermeture du programme, même bloqué en lecture.
    """

    def __init__(self) -> None:
        self._queue: asyncio.Queue[str | None] = asyncio.Queue()
        self._loop = asyncio.get_running_loop()
        threading.Thread(target=self._read, name="stdin", daemon=True).start()

    async def next(self) -> str | None:
        return await self._queue.get()

    def _read(self) -> None:
        while True:
            line = sys.stdin.readline()
            try:
                self._loop.call_soon_threadsafe(self._queue.put_nowait, line or None)
            except RuntimeError:  # boucle déjà fermée
                return
            if not line:
                return


@contextlib.contextmanager
def _cancel_on_ctrl_c(task: asyncio.Task[Any]) -> Iterator[None]:
    """Pendant un tour, Ctrl+C annule ce tour au lieu de quitter E.V.A."""
    loop = asyncio.get_running_loop()

    def on_sigint(signum: int, frame: object) -> None:
        loop.call_soon_threadsafe(task.cancel)

    previous = signal.signal(signal.SIGINT, on_sigint)
    try:
        yield
    finally:
        signal.signal(signal.SIGINT, previous)
