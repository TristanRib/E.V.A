"""Interface de discussion en terminal."""

from eva.core import Agent, AgentError
from eva.llm import LLMError

_HELP = "Commandes : /reset (nouvelle conversation), /quit (quitter)"


def _print_chunk(text: str) -> None:
    print(text, end="", flush=True)


def run_cli(agent: Agent, *, provider_name: str) -> None:
    print(f"E.V.A en ligne — {provider_name}")
    print(_HELP, end="\n\n")

    while True:
        try:
            text = input("Vous › ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not text:
            continue
        if text in {"/quit", "/exit"}:
            break
        if text == "/reset":
            agent.reset()
            print("— Nouvelle conversation —\n")
            continue

        print("EVA › ", end="", flush=True)
        try:
            agent.ask(text, on_text=_print_chunk)
        except (LLMError, AgentError) as e:
            print(f"\n[erreur] {e}\n")
            continue
        except KeyboardInterrupt:
            print("\n[interrompu]\n")
            continue

        print("\n")

    print("À bientôt.")
