# E.V.A — Entité Virtuelle d'Assistance

Assistant personnel inspiré de J.A.R.V.I.S : un LLM qui pilote des outils (domotique, système, …)
grâce au *function calling*.

Le LLM est **interchangeable** : un fournisseur cloud ou local (Ollama) se branche derrière une
abstraction, sans toucher au reste du code.

> **Statut :** en construction. Pour l'instant, interface texte uniquement ; le vocal viendra plus tard.

## Architecture

```
 Interface (terminal → web → vocal)
                │
                ▼
 ┌──────────────────────────────┐
 │  core : orchestrateur        │   boucle d'agent : message → LLM → outils → LLM → réponse
 └──────┬────────────────┬──────┘
        │                │
        ▼                ▼
   llm (fournisseur) tools (horloge, Hue, …)
```

| Module           | Rôle                                                                      |
|------------------|---------------------------------------------------------------------------|
| `eva.core`       | Boucle d'agent, historique de conversation, prompt système                |
| `eva.llm`        | Contrat `LLMProvider`, types neutres, et une implémentation par fournisseur |
| `eva.tools`      | Outils appelables par le LLM, chacun avec son schéma                      |
| `eva.interfaces` | Points d'entrée utilisateur (CLI pour commencer)                          |
| `eva.config`     | Configuration typée, lue depuis `.env`                                    |

### Changer de LLM

Le cœur d'E.V.A ne connaît que `eva.llm.LLMProvider` et des types neutres (`UserMessage`,
`AssistantMessage`, `ToolCall`…). Aucun type d'un SDK tiers ne sort de `eva.llm`.

- **Changer de modèle** : `EVA_MODEL` dans `.env`.
- **Changer de fournisseur** : `EVA_PROVIDER` dans `.env`.
- **Ajouter un fournisseur** : une classe qui implémente `LLMProvider` (voir
  [`llm/base.py`](src/eva/llm/base.py)) + une branche dans [`llm/factory.py`](src/eva/llm/factory.py).

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

### Philips Hue

Appairage, une seule fois : lancer la commande, puis appuyer sur le bouton du bridge dans les
30 secondes. L'IP du bridge et la clé obtenue sont enregistrées dans `.env`.

```bash
uv run eva-hue-pair
```

E.V.A dispose alors de trois outils :

| Outil                | Type     | Rôle                                                        |
|----------------------|----------|-------------------------------------------------------------|
| `hue_status`         | lecture  | État des pièces, zones, lampes et liste des scènes          |
| `hue_set_lights`     | action   | Allumer / éteindre / régler intensité et couleur            |
| `hue_activate_scene` | action   | Activer une scène                                           |

Les descriptions des outils distinguent explicitement **lecture** et **action** : un petit
modèle tend sinon à « consulter » les scènes en en activant une.

Les noms des lampes, pièces, zones et scènes sont lus sur le bridge au démarrage : le LLM ne
peut choisir que parmi des noms existants. Si le bridge est injoignable, E.V.A démarre sans
les outils Hue.

## Configuration

Toute la configuration passe par des variables d'environnement (fichier `.env`, jamais versionné).
Voir [`.env.example`](.env.example) pour la liste complète.

| Variable            | Description                                          | Défaut                   |
|---------------------|------------------------------------------------------|--------------------------|
| `EVA_PROVIDER`      | Fournisseur de LLM (`ollama`)                        | —                        |
| `EVA_MODEL`         | Modèle utilisé                                       | `qwen3:4b-instruct`      |
| `EVA_MAX_TOKENS`    | Longueur maximale d'une réponse (tokens)             | `1024`                   |
| `EVA_CONTEXT_SIZE`  | Fenêtre de contexte du LLM local (tokens)            | `8192`                   |
| `EVA_KEEP_ALIVE`    | Maintien du modèle en VRAM après usage (`-1` = toujours) | `30m`                |
| `EVA_HISTORY_TURNS` | Nombre d'échanges conservés dans la conversation     | `20`                     |
| `EVA_LOG_LEVEL`     | Niveau de log (`INFO` affiche les appels d'outils)   | `WARNING`                |
| `OLLAMA_HOST`       | URL du serveur Ollama                                | `http://localhost:11434` |
| `HUE_BRIDGE_IP`     | IP du bridge Philips Hue sur le réseau local         | —                        |
| `HUE_APP_KEY`       | Clé d'application Hue (obtenue à l'appairage)        | —                        |

Commandes disponibles dans le chat : `/reset` (nouvelle conversation), `/quit`.

## Développement

```bash
uv run ruff check .        # lint
uv run ruff format .       # formatage
uv run mypy                # typage (mode strict)
uv run pytest              # tests
```

### Structure du dépôt

```
E.V.A/
├── src/eva/
│   ├── __main__.py      # point d'entrée (`eva` / `python -m eva`)
│   ├── config.py        # configuration typée
│   ├── core/            # orchestrateur : agent.py, prompts.py
│   ├── llm/             # types.py, base.py, factory.py, ollama.py
│   ├── tools/           # base.py (registre), clock.py
│   │   └── hue/         # client.py (API CLIP v2), home.py, tools.py, pairing.py
│   └── interfaces/      # cli.py, puis web / vocal
├── tests/
├── .env.example
└── pyproject.toml
```

## Feuille de route

- [x] Chat texte en terminal, abstraction du LLM
- [x] Boucle d'agent avec function calling (outil de test : date et heure)
- [x] Premier fournisseur de LLM : Ollama (local)
- [x] Contrôle des lampes **Philips Hue** (état, réglages, scènes)
- [ ] Client MCP pour brancher des serveurs d'outils externes
- [ ] Mémoire long terme
- [ ] Interface web
- [ ] Voix : reconnaissance (STT), synthèse (TTS), mot de réveil
