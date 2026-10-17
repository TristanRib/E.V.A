"""Historique d'une conversation et politique de rétention.

C'est ici que se branchera la future mémoire long terme.
"""

from eva.domain import Message, UserMessage


class Conversation:
    def __init__(self, *, max_turns: int = 20) -> None:
        self._max_turns = max_turns
        self._messages: list[Message] = []

    @property
    def messages(self) -> tuple[Message, ...]:
        return tuple(self._messages)

    def append(self, message: Message) -> None:
        self._messages.append(message)

    def checkpoint(self) -> int:
        """Point de retour, à passer à `rollback()`."""
        return len(self._messages)

    def rollback(self, checkpoint: int) -> None:
        del self._messages[checkpoint:]

    def clear(self) -> None:
        self._messages.clear()

    def trim(self) -> None:
        """Ne garde que les `max_turns` derniers échanges.

        On coupe toujours au début d'un échange (message utilisateur), pour ne jamais
        séparer un appel d'outil de son résultat.
        """
        turn_starts = [i for i, m in enumerate(self._messages) if isinstance(m, UserMessage)]
        excess = len(turn_starts) - self._max_turns
        if excess > 0:
            del self._messages[: turn_starts[excess]]
