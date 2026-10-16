# E.V.A — Entité Virtuelle d'Assistance

Assistant personnel inspiré de J.A.R.V.I.S : un LLM qui pilote des outils (domotique, système, …)
grâce au *function calling*.

- **LLM interchangeable** : local (Ollama) ou cloud, derrière une abstraction.
- **Capacités en plugins** : chaque intégration (Hue, horloge…) est un paquet autonome.
- **Asynchrone** : prêt pour le vocal, les rappels et les tâches en parallèle.

> **Statut :** en construction. Interface texte uniquement pour l'instant ; le vocal viendra plus tard.

## Architecture

```
            interfaces (terminal → web → vocal)
                          │  événements
                          ▼
   app.py ──────►  agent  (boucle LLM ↔ outils, conversation, prompt)
 (assemblage)      │    │
                   ▼    ▼
                 llm    plugins (clock, hue, …)
                   ╲    ╱
                   domain  (messages, outils, erreurs : dépend de rien)
```

| Paquet            | Rôle                                                                        |
|-------------------|-----------------------------------------------------------------------------|
| `eva.domain`      | Noyau sans dépendance : messages, contrat `Tool`, erreurs                   |
| `eva.llm`         | Contrat `LLMProvider` + une implémentation par fournisseur (`providers/`)   |
| `eva.agent`       | `Agent` (boucle), `Conversation` (historique), `Toolbox` (exécution des outils), événements, prompt |
| `eva.plugins`     | Capacités d'E.V.A, une par sous-paquet, et leur chargement                   |
| `eva.interfaces`  | Points d'entrée utilisateur : terminal aujourd'hui                          |
| `eva.app`         | Racine de composition : le seul module qui assemble les pièces concrètes    |
| `eva.config`      | Réglages du cœur (`EVA_*`) et classe de base des réglages de chaque composant |

**Sens des dépendances :** `domain` ← `llm`, `plugins` ← `agent` ← `interfaces` ← `app`.
`domain` n'importe rien d'autre d'E.V.A, et seul `app` connaît les classes concrètes.

### Principes

- **Un outil = une classe** qui déclare son nom, sa description, son **effet**
  (`READ` ou `ACTION`) et ses arguments sous forme de **modèle pydantic**. Le schéma envoyé au
  LLM en est généré, et les arguments sont validés avant exécution.
- **Lecture / action** : la description de chaque outil est préfixée automatiquement de
  `[LECTURE SEULE]` ou `[ACTION]`. Le prompt pose une règle générique : pas d'action sans
  demande explicite. Aucune consigne propre à un outil n'est mise dans le prompt.
- **Erreurs** : un outil lève `ToolError` pour un échec attendu (message transmis au LLM). Un
  plugin indisponible (non configuré, service injoignable) est ignoré au démarrage, sans
  bloquer E.V.A.
- **Événements** : l'agent émet `TextDelta`, `ToolCallStarted`, `ToolCallFinished`,
  `TurnFinished`. Les interfaces et la journalisation s'y abonnent.

### Ajouter un plugin

1. Créer `src/eva/plugins/<nom>/` avec :
   - `tools.py` : une classe par outil, héritant de `Tool[Args]` ;
   - `plugin.py` : une classe avec `name` et `async create_tools(resources)`, qui lit ses
     réglages (`<Nom>Settings(EvaBaseSettings)`), prépare ses clients et renvoie ses outils ;
     lever `PluginUnavailable` s'il ne peut pas fonctionner.
2. L'ajouter à `PLUGINS` dans [`plugins/registry.py`](src/eva/plugins/registry.py).
3. Écrire ses tests dans `tests/plugins/<nom>/`.

Exemple minimal : [`plugins/clock/`](src/eva/plugins/clock/).

### Ajouter un fournisseur de LLM

Une classe qui implémente `LLMProvider` ([`llm/provider.py`](src/eva/llm/provider.py)) dans
`llm/providers/`, plus une branche dans [`llm/factory.py`](src/eva/llm/factory.py).

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
cp .env.example .env   # puis compléter les valeurs
```

## Utilisation

```bash
uv run eva
```

Commandes dans le chat : `/reset` (nouvelle conversation), `/quit`. Ctrl+C pendant une
réponse l'interrompt sans quitter E.V.A.

### Plugin Philips Hue

Appairage, une seule fois : lancer la commande, puis appuyer sur le bouton du bridge dans les
30 secondes. L'IP du bridge et la clé obtenue sont enregistrées dans `.env`.

```bash
uv run eva-hue-pair
```

| Outil                | Effet   | Rôle                                                |
|----------------------|---------|-----------------------------------------------------|
| `hue_status`         | lecture | État des pièces, zones, lampes et liste des scènes  |
| `hue_set_lights`     | action  | Allumer / éteindre / régler intensité et couleur    |
| `hue_activate_scene` | action  | Activer une scène                                   |

Les noms des lampes, pièces, zones et scènes sont lus sur le bridge au démarrage : le LLM ne
peut choisir que parmi des noms existants (casse et accents tolérés).

## Configuration

Toute la configuration passe par le fichier `.env` (jamais versionné). Chaque composant lit
ses propres variables ; voir [`.env.example`](.env.example).

| Variable              | Description                                            | Défaut                   |
|-----------------------|--------------------------------------------------------|--------------------------|
| `EVA_PROVIDER`        | Fournisseur de LLM (`ollama`)                          | —                        |
| `EVA_MODEL`           | Modèle utilisé                                         | `qwen3:4b-instruct`      |
| `EVA_MAX_TOKENS`      | Longueur maximale d'une réponse (tokens)               | `1024`                   |
| `EVA_USER_NAME`       | Prénom utilisé par E.V.A                               | `Tristan`                |
| `EVA_HISTORY_TURNS`   | Nombre d'échanges conservés dans la conversation       | `20`                     |
| `EVA_PLUGINS`         | Plugins activés (`clock,hue`)                          | tous                     |
| `EVA_LOG_LEVEL`       | Niveau de log (`INFO` affiche les appels d'outils)     | `WARNING`                |
| `OLLAMA_HOST`         | URL du serveur Ollama                                  | `http://localhost:11434` |
| `OLLAMA_CONTEXT_SIZE` | Fenêtre de contexte (tokens)                           | `8192`                   |
| `OLLAMA_KEEP_ALIVE`   | Maintien du modèle en VRAM (`-1` = toujours)           | `30m`                    |
| `HUE_BRIDGE_IP`       | IP du bridge Philips Hue                               | —                        |
| `HUE_APP_KEY`         | Clé d'application Hue (obtenue à l'appairage)          | —                        |

## Développement

```bash
uv run ruff check .        # lint
uv run ruff format .       # formatage
uv run mypy                # typage (mode strict)
uv run pytest              # tests (arborescence miroir de src/, doublures dans tests/fakes.py)
```

### Structure du dépôt

```
src/eva/
├── __main__.py            # point d'entrée (`eva`)
├── app.py                 # racine de composition
├── config.py              # EvaBaseSettings, EvaSettings
├── domain/                # errors.py, messages.py, text.py, tools.py
├── agent/                 # agent.py, conversation.py, toolbox.py, events.py, prompt.py
├── llm/                   # provider.py, factory.py, providers/ollama.py
├── plugins/               # base.py, registry.py
│   ├── clock/             # plugin.py, tools.py
│   └── hue/               # plugin.py, settings.py, client.py, home.py, tools.py, pairing.py
└── interfaces/            # cli.py
```

## Feuille de route

- [x] Chat texte en terminal, abstraction du LLM
- [x] Boucle d'agent avec function calling
- [x] Premier fournisseur de LLM : Ollama (local)
- [x] Contrôle des lampes **Philips Hue** (état, réglages, scènes)
- [x] Architecture en plugins, asynchrone, orientée événements
- [ ] Client MCP pour brancher des serveurs d'outils externes
- [ ] Mémoire long terme
- [ ] Interface web
- [ ] Voix : reconnaissance (STT), synthèse (TTS), mot de réveil
