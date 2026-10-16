"""Point d'entrée : `python -m eva` ou `eva`."""

import logging

from pydantic import ValidationError

from eva.config import Settings
from eva.core import SYSTEM_PROMPT, Agent
from eva.interfaces.cli import run_cli
from eva.llm import LLMError, create_provider
from eva.tools import default_tools


def main() -> None:
    try:
        settings = Settings()
        llm = create_provider(settings)
    except ValidationError as e:
        raise SystemExit(f"[configuration] Valeur invalide dans .env :\n{e}") from e
    except LLMError as e:
        raise SystemExit(f"[configuration] {e}") from e

    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    agent = Agent(llm, default_tools(settings), SYSTEM_PROMPT, max_turns=settings.history_turns)
    run_cli(agent, provider_name=llm.name)


if __name__ == "__main__":
    main()
