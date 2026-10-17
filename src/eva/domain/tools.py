"""Définition d'un outil : ce qu'E.V.A sait faire, présenté au LLM.

Un outil déclare ses arguments sous forme de modèle pydantic : le schéma JSON envoyé
au LLM en est généré, et les arguments reçus sont validés contre lui avant exécution.
"""

from abc import ABC, abstractmethod
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Annotated, Any, ClassVar, Literal, cast

from pydantic import BaseModel, BeforeValidator, ConfigDict, create_model

from eva.domain.text import normalize


class ToolEffect(StrEnum):
    """Ce qu'un outil fait au monde réel ; chaque outil doit le déclarer."""

    READ = "read"
    """Consulte uniquement, sans rien modifier."""
    ACTION = "action"
    """Modifie l'état du monde réel ou déclenche quelque chose."""


@dataclass(frozen=True, slots=True)
class ToolSpec:
    """Description d'un outil telle que présentée au LLM."""

    name: str
    description: str
    input_schema: dict[str, Any]
    """Schéma JSON (type `object`) des arguments attendus."""
    effect: ToolEffect


class NoArgs(BaseModel):
    """Arguments d'un outil qui n'en prend aucun."""

    model_config = ConfigDict(extra="ignore")


class Tool[ArgsT: BaseModel](ABC):
    """Capacité d'E.V.A que le LLM peut déclencher.

    Une sous-classe définit `name`, `description`, `effect`, `args_model` et `run()`.
    `name`, `description` et `args_model` peuvent être fixés sur la classe ou dans
    `__init__` (valeurs connues seulement à l'exécution) ; `effect` est fixé sur la classe.
    """

    name: str
    description: str
    effect: ClassVar[ToolEffect]
    args_model: type[ArgsT]

    def spec(self) -> ToolSpec:
        schema = _clean_schema(self.args_model.model_json_schema())
        return ToolSpec(self.name, self.description, schema, self.effect)

    def parse_args(self, arguments: Mapping[str, Any]) -> ArgsT:
        """Valide les arguments reçus du LLM (lève `pydantic.ValidationError`)."""
        return self.args_model.model_validate(arguments)

    @abstractmethod
    async def run(self, args: ArgsT) -> str:
        """Exécute l'outil et renvoie un résultat textuel destiné au LLM.

        Lever `ToolError` pour un échec attendu : son message est transmis au LLM.
        """


def choice(values: Iterable[str], *, aliases: Mapping[str, str] | None = None) -> Any:
    """Type d'argument limité à `values`, tolérant casse, accents et alias.

    Dans le schéma, le LLM voit la liste exacte (`enum`) ; à la validation, une valeur
    écrite avec une autre casse ou sans accents est ramenée à sa forme canonique.

    La liste doit couvrir tout ce que l'utilisateur peut désigner : faute de pouvoir
    exprimer une valeur absente, le LLM tend à choisir la plus proche, et donc à agir
    sur autre chose que ce qui était demandé.
    """
    canonical = {normalize(v): v for v in values}
    canonical.update({normalize(alias): target for alias, target in (aliases or {}).items()})

    def to_canonical(value: object) -> object:
        return canonical.get(normalize(value), value) if isinstance(value, str) else value

    allowed = Literal[tuple(dict.fromkeys(canonical.values()))]  # type: ignore[valid-type]
    return Annotated[allowed, BeforeValidator(to_canonical)]


def with_choices[ModelT: BaseModel](base: type[ModelT], **choices: Any) -> type[ModelT]:
    """Dérive `base` en restreignant des champs `str` aux choix donnés (voir `choice()`).

    Les arguments restent typés statiquement par `base` ; seuls le schéma et la validation
    connaissent les valeurs, souvent connues seulement à l'exécution.
    """
    overrides: dict[str, Any] = {}
    for field_name, allowed in choices.items():
        field = base.model_fields[field_name]
        annotation = allowed if field.is_required() else allowed | None
        overrides[field_name] = (annotation, field)
    return cast(
        "type[ModelT]",
        create_model(base.__name__, __base__=base, **overrides),
    )


def _clean_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Allège le schéma généré par pydantic pour les petits modèles.

    Retire les titres et simplifie les champs optionnels (`X | None = None` → `X`).
    """
    properties: dict[str, Any] = {}
    for name, prop in schema.get("properties", {}).items():
        prop = {k: v for k, v in prop.items() if k != "title"}
        variants = prop.pop("anyOf", None)
        if variants is not None:
            non_null = [v for v in variants if v.get("type") != "null"]
            if len(non_null) == 1:
                prop = {**non_null[0], **prop}
            else:
                prop["anyOf"] = variants
            if prop.get("default", ...) is None:
                del prop["default"]
        if "const" in prop:  # choix à valeur unique : toujours présenté comme une liste
            prop["enum"] = [prop.pop("const")]
        properties[name] = prop

    cleaned: dict[str, Any] = {"type": "object", "properties": properties}
    if required := schema.get("required"):
        cleaned["required"] = required
    return cleaned
