"""Date et heure locales."""

from datetime import datetime
from typing import Any

from eva.llm import ToolEffect, ToolSpec

# Noms en dur plutôt que la locale système, qui varie d'une machine à l'autre.
_WEEKDAYS = ("lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche")
_MONTHS = (
    "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre",
)  # fmt: skip


def format_datetime(moment: datetime) -> str:
    """Ex. : « samedi 17 octobre 2026, 00:23 (UTC+02:00) ».

    Le jour de la semaine est calculé ici : les petits modèles le devinent souvent mal.
    """
    weekday = _WEEKDAYS[moment.weekday()]
    month = _MONTHS[moment.month - 1]
    offset = moment.strftime("%z")
    return (
        f"{weekday} {moment.day} {month} {moment.year}, {moment:%H:%M} "
        f"(UTC{offset[:3]}:{offset[3:]})"
    )


class ClockTool:
    spec = ToolSpec(
        name="get_current_datetime",
        description="Renvoie la date (avec le jour de la semaine) et l'heure locales actuelles.",
        input_schema={"type": "object", "properties": {}},
        effect=ToolEffect.READ,
    )

    def run(self, arguments: dict[str, Any]) -> str:
        return format_datetime(datetime.now().astimezone())
