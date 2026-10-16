# E.V.A — Entité Virtuelle d'Assistance

Assistant personnel inspiré de J.A.R.V.I.S : un LLM qui pilote des outils (domotique, système, …)
grâce au *function calling*.

- **LLM interchangeable** : local (Ollama) ou cloud, derrière une abstraction.
- **Capacités en plugins** : chaque intégration (Hue, horloge…) est un paquet autonome.
- **Asynchrone** : prêt pour le vocal, les rappels et les tâches en parallèle.

> **Statut :** en construction. Interface texte uniquement pour l'instant ; le vocal viendra plus tard.

## Architecture

Le cœur et chaque plugin suivent **la même architecture en couches, avec les mêmes noms** :
un plugin est un E.V.A en miniature.

| Couche | Cœur d'E.V.A | Plugin | Règle |
|---|---|---|---|
| Domaine | `domain/` | `domain.py` | Entités et règles pures ; n'importe rien du projet (sauf `eva.domain` pour un plugin) |
| Configuration | `config.py` | `config.py` | Schéma de sa section d'`eva.toml` + noms de ses secrets |
| Accès externe | `llm/` | `client.py` | Seul à connaître le format externe ; traduit externe ↔ domaine |
| Application | `agent/` | `service.py` | Logique applicative, utilisable sans LLM |
| Points d'entrée | `interfaces/` | `tools.py`, `cli.py` | Adaptateurs vers le LLM (outils) ou l'humain (commandes) |
| Assemblage | `app.py` | `plugin.py` | Instancie et relie ; aucune logique |

Les dépendances vont toujours dans le même sens : points d'entrée → application →
accès externe → domaine.

```
            interfaces (terminal → web → vocal)
                          │  événements
                          ▼
   app.py ──────►  agent  (boucle LLM ↔ outils, conversation, prompt)
 (assemblage)      │    │
                   ▼    ▼
                 llm    plugins (clock, hue, …)
                   ╲    ╱
                   domain  (messages, contrat Tool, erreurs)
```

### Principes

- **Un outil = une classe** qui déclare son nom, sa description, son **effet** (`READ` ou
  `ACTION`) et ses arguments sous forme de **modèle pydantic**. Le schéma envoyé au LLM en est
  généré, et les arguments sont validés avant exécution. Les choix dynamiques (noms de
  lampes…) passent par `with_choices()`.
- **Lecture / action** : la description de chaque outil est préfixée automatiquement de
  `[LECTURE SEULE]` ou `[ACTION]`. Le prompt pose une règle générique : pas d'action sans
  demande explicite. Aucune consigne propre à un outil n'est mise dans le prompt.
- **Erreurs** : toute `EvaError` est un échec attendu, dont le message est lisible ; s'il
  survient pendant un appel d'outil, il est transmis tel quel au LLM. Un plugin indisponible
  est ignoré au démarrage, sans bloquer E.V.A.
- **N sites, un jeu d'outils** : un plugin gère toutes ses instances (plusieurs maisons, plus
  tard plusieurs comptes) avec un seul jeu d'outils et un argument optionnel pour lever
  l'ambiguïté, plutôt que de dupliquer les outils.
- **Événements** : l'agent émet `TextDelta`, `ToolCallStarted`, `ToolCallFinished`,
  `TurnFinished`. Les interfaces et la journalisation s'y abonnent.

### Ajouter un plugin

```
src/eva/plugins/<nom>/
├── __init__.py   # exporte la classe Plugin, rien d'autre
├── plugin.py     # obligatoire : Plugin[Config] avec config_model et async setup(context)
├── tools.py      # obligatoire : une classe Tool[Args] par outil
├── config.py     # section [plugins.<nom>] + noms des secrets
├── domain.py     # entités du plugin
├── client.py     # API externe ↔ domaine
├── service.py    # opérations du plugin
└── cli.py        # commandes annexes (appairage, connexion…)
```

1. Créer le paquet avec les couches nécessaires. Seuls `plugin.py` et `tools.py` sont
   obligatoires. `setup(context)` reçoit `context.config` (sa section d'`eva.toml`, déjà
   validée), `context.secrets` et `context.resources` (ressources à fermer à l'arrêt). Il
   renvoie les outils, ou lève `PluginUnavailable`.
2. L'ajouter à `PLUGINS` dans [`plugins/registry.py`](src/eva/plugins/registry.py)
   (`"nom": "eva.plugins.nom:NomPlugin"`). Il n'est importé que s'il est activé.
3. Écrire ses tests dans `tests/plugins/<nom>/`, une suite par couche.

Exemples : [`plugins/clock/`](src/eva/plugins/clock/) (minimal),
[`plugins/hue/`](src/eva/plugins/hue/) (toutes les couches).

### Ajouter un fournisseur de LLM

Une classe qui implémente `LLMProvider` ([`llm/provider.py`](src/eva/llm/provider.py)) dans
`llm/providers/`, avec sa configuration (section `[llm.<nom>]`), plus une branche dans
[`llm/factory.py`](src/eva/llm/factory.py).

## Prérequis

- **Python 3.12+**
- **[uv](https://docs.astral.sh/uv/)** pour gérer l'environnement et les dépendances
- **[Ollama](https://ollama.com/download)** pour faire tourner le LLM en local

## Installation

```bash
# 1. Dépendances Python (crée .venv automatiquement)
uv sync

# 2. Modèle local (~2,5 Go, tient sur un GPU de 8 Go)
ollama pull qwen3:4b-instruct

# 3. Configuration locale
cp eva.example.toml eva.toml   # structure : modèle, plugins, maisons…
cp .env.example .env           # secrets uniquement
```

## Utilisation

```bash
uv run eva
```

Commandes dans le chat : `/reset` (nouvelle conversation), `/quit`. Ctrl+C pendant une
réponse l'interrompt sans quitter E.V.A.

### Plugin Philips Hue

Appairage d'une maison : lancer la commande, puis appuyer sur le bouton du bridge dans les
30 secondes. La maison est ajoutée à `eva.toml` (commentaires préservés), sa clé à `.env`.

```bash
uv run eva-hue-pair                     # maison « Maison », bridge découvert automatiquement
uv run eva-hue-pair --name Chalet       # une autre maison
uv run eva-hue-pair --name Chalet --ip 10.0.0.5
```

| Outil                | Effet   | Rôle                                                |
|----------------------|---------|-----------------------------------------------------|
| `hue_status`         | lecture | État des pièces, zones, lampes et scènes            |
| `hue_set_lights`     | action  | Allumer / éteindre / régler intensité et couleur    |
| `hue_activate_scene` | action  | Activer une scène                                   |

Les noms des lampes, pièces, zones et scènes de toutes les maisons sont lus au démarrage : le
LLM ne peut choisir que parmi des noms existants (casse et accents tolérés). Avec plusieurs
maisons, la maison n'est à préciser que si le nom existe dans plusieurs d'entre elles. Une
maison injoignable est ignorée, les autres restent utilisables.

## Configuration

| Fichier | Contenu | Versionné |
|---|---|---|
| `eva.toml` | Structure : prénom, LLM, plugins, maisons… (voir [`eva.example.toml`](eva.example.toml)) | non |
| `.env` | Secrets uniquement : `HUE_KEY_<MAISON>`… (voir [`.env.example`](.env.example)) | jamais |

Toute valeur d'`eva.toml` peut être surchargée par l'environnement, préfixe `EVA_` et `__`
pour une sous-section : `EVA_LOG_LEVEL=INFO uv run eva`, `EVA_LLM__MODEL=…`. Le fichier de
configuration peut être choisi avec `EVA_CONFIG`.

## Développement

```bash
uv run ruff check .        # lint
uv run ruff format .       # formatage
uv run mypy                # typage strict (sources et tests)
uv run pytest              # tests (arborescence miroir de src/, doublures dans tests/fakes*.py)
```

## Feuille de route

- [x] Chat texte en terminal, abstraction du LLM
- [x] Boucle d'agent avec function calling
- [x] Premier fournisseur de LLM : Ollama (local)
- [x] Contrôle des lampes **Philips Hue** (état, réglages, scènes, plusieurs maisons)
- [x] Architecture en couches et en plugins, asynchrone, orientée événements
- [ ] Client MCP pour brancher des serveurs d'outils externes
- [ ] Mémoire long terme
- [ ] Interface web
- [ ] Voix : reconnaissance (STT), synthèse (TTS), mot de réveil
