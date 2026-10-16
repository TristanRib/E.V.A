"""Fournisseur Ollama (LLM local)."""

import uuid
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

import ollama

from eva.llm.base import LLMError, TextCallback
from eva.llm.types import (
    AssistantMessage,
    Completion,
    Message,
    StopReason,
    ToolCall,
    ToolResultsMessage,
    ToolSpec,
    UserMessage,
)

# Variante « instruct » : répond directement, sans phase de réflexion (rapide).
DEFAULT_MODEL = "qwen3:4b-instruct"
DEFAULT_HOST = "http://localhost:11434"


class OllamaProvider:
    def __init__(
        self,
        *,
        model: str = DEFAULT_MODEL,
        host: str = DEFAULT_HOST,
        max_tokens: int = 1024,
        context_size: int = 8192,
        keep_alive: str = "30m",
        think: bool = False,
    ) -> None:
        self._client = ollama.Client(host=host)
        self._model = model
        self._host = host
        self._max_tokens = max_tokens
        # Sans valeur explicite, Ollama applique son propre défaut (4096) et, au-delà,
        # supprime silencieusement les messages les plus anciens de la conversation.
        self._context_size = context_size
        # Durée pendant laquelle le modèle reste en VRAM après une requête : évite de le
        # recharger (plusieurs secondes) à chaque message espacé.
        self._keep_alive = keep_alive
        # Le mode « réflexion » des modèles qui le proposent (Qwen3…) améliore un peu les
        # réponses complexes mais rallonge nettement le délai : désactivé par défaut.
        self._think = think

    @property
    def name(self) -> str:
        return f"ollama ({self._model})"

    def complete(
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
            stream = self._client.chat(
                model=self._model,
                messages=[
                    ollama.Message(role="system", content=system),
                    *_to_api_messages(messages),
                ],
                tools=[_to_api_tool(t) for t in tools],
                think=self._think,
                stream=True,
                keep_alive=self._keep_alive,
                options={"num_ctx": self._context_size, "num_predict": self._max_tokens},
            )
            for chunk in stream:
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
                    f"(installe-le avec `ollama pull {self._model}`)."
                ) from e
            raise LLMError(f"Erreur d'Ollama ({e.status_code}) : {e.error}") from e
        except ConnectionError as e:
            raise LLMError(f"Impossible de joindre Ollama sur {self._host} : est-il lancé ?") from e
        except ollama.RequestError as e:
            raise LLMError(f"Requête Ollama invalide : {e.error}") from e

        return _to_completion("".join(text_parts), api_tool_calls, done_reason)


def _to_api_tool(spec: ToolSpec) -> Mapping[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": spec.name,
            "description": spec.tagged_description,
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
