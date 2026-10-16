"""Fournisseur Ollama (LLM local)."""

import uuid
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

import ollama
from pydantic import BaseModel, ConfigDict, Field

from eva.domain import (
    AssistantMessage,
    Message,
    ToolCall,
    ToolResultsMessage,
    ToolSpec,
    UserMessage,
)
from eva.llm.provider import Completion, LLMError, StopReason, TextCallback, describe_tool

# Variante « instruct » : répond directement, sans phase de réflexion (rapide).
DEFAULT_MODEL = "qwen3:4b-instruct"


class OllamaConfig(BaseModel):
    """Section `[llm.ollama]` d'`eva.toml`."""

    model_config = ConfigDict(extra="forbid")

    host: str = "http://localhost:11434"
    context_size: int = Field(default=8192, ge=2048)
    """Fenêtre de contexte en tokens (plus grand = mémoire plus longue, plus de VRAM)."""
    keep_alive: str = "30m"
    """Durée de maintien du modèle en VRAM après usage (`30m`, `2h`, `-1` = toujours)."""


class OllamaProvider:
    def __init__(
        self,
        config: OllamaConfig,
        *,
        model: str = DEFAULT_MODEL,
        max_tokens: int = 1024,
    ) -> None:
        self._client = ollama.AsyncClient(host=config.host)
        self._config = config
        self._model = model
        self._max_tokens = max_tokens

    @property
    def name(self) -> str:
        return f"ollama ({self._model})"

    async def complete(
        self,
        *,
        system: str,
        messages: Sequence[Message],
        tools: Sequence[ToolSpec],
        on_text: TextCallback | None = None,
    ) -> Completion:
        text_parts: list[str] = []
        api_tool_calls: list[ollama.Message.ToolCall] = []
        done_reason: str | None = None

        try:
            stream = await self._client.chat(
                model=self._model,
                messages=[
                    ollama.Message(role="system", content=system),
                    *_to_api_messages(messages),
                ],
                tools=[_to_api_tool(t) for t in tools],
                # Pas de phase de « réflexion » pour les modèles qui la proposent : elle
                # rallonge nettement le délai pour un gain faible sur des réponses courtes.
                think=False,
                stream=True,
                # Sans valeur explicite, Ollama limite le contexte à 4096 tokens et
                # supprime silencieusement les messages les plus anciens au-delà.
                options={"num_ctx": self._config.context_size, "num_predict": self._max_tokens},
                # Garde le modèle en VRAM entre deux messages (rechargement = plusieurs secondes).
                keep_alive=self._config.keep_alive,
            )
            async for chunk in stream:
                if chunk.message.content:
                    text_parts.append(chunk.message.content)
                    if on_text:
                        on_text(chunk.message.content)
                api_tool_calls.extend(chunk.message.tool_calls or ())
                if chunk.done:
                    done_reason = chunk.done_reason
        except ollama.ResponseError as e:
            if e.status_code == 404:
                raise LLMError(
                    f"Modèle absent d'Ollama : {self._model} "
                    f"(installez-le avec `ollama pull {self._model}`)."
                ) from e
            raise LLMError(f"Erreur d'Ollama ({e.status_code}) : {e.error}") from e
        except ConnectionError as e:
            raise LLMError(
                f"Impossible de joindre Ollama sur {self._config.host} : est-il lancé ?"
            ) from e
        except ollama.RequestError as e:
            raise LLMError(f"Requête Ollama invalide : {e.error}") from e

        return _to_completion("".join(text_parts), api_tool_calls, done_reason)

    async def aclose(self) -> None:
        await self._client.close()  # type: ignore[no-untyped-call]  # non annoté par la lib


def _to_api_tool(spec: ToolSpec) -> Mapping[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": spec.name,
            "description": describe_tool(spec),
            "parameters": spec.input_schema,
        },
    }


def _to_api_messages(messages: Iterable[Message]) -> list[ollama.Message]:
    # Ollama identifie un résultat d'outil par le nom de l'outil, pas par l'id de l'appel.
    tool_names: dict[str, str] = {}
    api_messages: list[ollama.Message] = []

    for message in messages:
        match message:
            case UserMessage(text=text):
                api_messages.append(ollama.Message(role="user", content=text))
            case AssistantMessage(text=text, tool_calls=calls):
                tool_names.update((c.id, c.name) for c in calls)
                api_messages.append(
                    ollama.Message(
                        role="assistant",
                        content=text,
                        tool_calls=[
                            ollama.Message.ToolCall(
                                function=ollama.Message.ToolCall.Function(
                                    name=c.name, arguments=c.arguments
                                )
                            )
                            for c in calls
                        ]
                        or None,
                    )
                )
            case ToolResultsMessage(results=results):
                api_messages.extend(
                    ollama.Message(
                        role="tool",
                        content=f"Erreur : {r.content}" if r.is_error else r.content,
                        tool_name=tool_names.get(r.call_id),
                    )
                    for r in results
                )

    return api_messages


def _to_completion(
    text: str,
    api_tool_calls: Iterable[ollama.Message.ToolCall],
    done_reason: str | None,
) -> Completion:
    # Ollama ne numérote pas les appels d'outils : on leur attribue un id unique.
    tool_calls = tuple(
        ToolCall(
            id=f"call_{uuid.uuid4().hex[:12]}",
            name=call.function.name,
            arguments=dict(call.function.arguments),
        )
        for call in api_tool_calls
    )
    message = AssistantMessage(text=text, tool_calls=tool_calls)

    if tool_calls:
        stop_reason = StopReason.TOOL_USE
    elif done_reason == "length":
        stop_reason = StopReason.MAX_TOKENS
    else:
        stop_reason = StopReason.END_TURN
    return Completion(message=message, stop_reason=stop_reason)
