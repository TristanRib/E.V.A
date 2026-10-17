"""Racine de composition : le seul module qui assemble les pièces concrètes d'E.V.A.

Aucune logique métier ici : configuration → LLM → plugins → agent → interface.
"""

import logging
from contextlib import AsyncExitStack

from pydantic import ValidationError

from eva.application import Agent, Conversation, LoggingSink, Toolbox, build_system_prompt
from eva.config import EvaSettings, Secrets, config_path
from eva.domain import ConfigurationError
from eva.infrastructure.llm import create_provider
from eva.interfaces import CliInterface
from eva.plugins import load_plugins


async def run() -> None:
    try:
        settings = EvaSettings()
        llm = create_provider(settings.llm)
    except ValidationError as e:
        raise SystemExit(f"[configuration] Valeur invalide dans {config_path()} :\n{e}") from e
    except ConfigurationError as e:
        raise SystemExit(f"[configuration] {e}") from e

    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    # Une ligne par requête HTTP noierait les journaux utiles ; visibles en DEBUG seulement.
    if settings.log_level != "DEBUG":
        logging.getLogger("httpx").setLevel(logging.WARNING)

    async with AsyncExitStack() as resources:
        resources.push_async_callback(llm.aclose)
        tools = await load_plugins(settings.plugins, Secrets.load(), resources)

        agent = Agent(
            llm,
            Toolbox(tools),
            build_system_prompt(settings.user_name),
            Conversation(max_turns=settings.history_turns),
            observers=[LoggingSink()],
        )
        await CliInterface(agent, title=llm.name).run()
