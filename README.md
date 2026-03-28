# 🌴 GwadaBot

> **Bot d'import OSM pour la Guadeloupe** — Powered by IGN BD TOPO® 2024

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://python.org)
[![Licence Ouverte 2.0](https://img.shields.io/badge/source-Licence%20Ouverte%202.0-green.svg)](https://www.etalab.gouv.fr/licence-ouverte-open-licence)
[![ODbL Compatible](https://img.shields.io/badge/ODbL-compatible-brightgreen.svg)](https://opendatacommons.org/licenses/odbl/)
[![OSM Import](https://img.shields.io/badge/OSM-import-orange.svg)](https://wiki.openstreetmap.org/wiki/Import/GwadaBot)

---

La Guadeloupe est l'un des territoires français les **moins bien maintenus sur OpenStreetMap**.
Plus de 60% des routes n'ont pas été modifiées depuis 2015.

**GwadaBot** corrige ça proprement, en une campagne d'import structurée depuis la
BD TOPO® IGN — la référence topographique officielle de la France à précision métrique.

```
╔══════════════════════════════════════════════╗
║  IGN BD TOPO® 2024 → Conflation → OSM 🗺️   ║
║  Routes · Hydrographie · Bâtiments          ║
║  Guadeloupe entière — ~200 000 objets        ║
╚══════════════════════════════════════════════╝
```

---

## 📦 Structure du projet

```
gwadabot/
├── scripts/
│   ├── gwadabot.py      ← Bot principal (pipeline complet)
│   ├── conflation.py    ← Moteur de conflation IGN ↔ OSM
│   └── analyze.py       ← Analyse préliminaire de l'état OSM
├── data/                ← BD TOPO® téléchargée ici (gitignored)
├── logs/                ← Fichiers .osc générés + logs
├── wiki/
│   └── WIKI_OSM_PAGE.md ← Page à publier sur wiki.openstreetmap.org
├── requirements.txt
└── README.md
```

---

## 🚀 Installation

### Prérequis système

```bash
# macOS
brew install 7zip gdal

# Ubuntu/Debian
sudo apt install p7zip-full gdal-bin

# Python 3.11+
python --version
```

### Installation Python

```bash
git clone https://github.com/VOTRE_PSEUDO/gwadabot
cd gwadabot

python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

pip install -r requirements.txt
```

---

## 🔐 Authentification OSM (OAuth 2.0)

Depuis juillet 2024, OSM **exige OAuth 2.0** (plus de user/password).

### Étape 1 — Créer un compte bot OSM

1. Créez un compte sur [openstreetmap.org](https://openstreetmap.org) nommé `GwadaBot`
2. Dans les paramètres → Applications OAuth → **Enregistrer une nouvelle application**
3. Notez le `client_id` et `client_secret`

### Étape 2 — Obtenir un access token

```bash
pip install oauthcli

python -c "
from oauthcli import OpenStreetMapAuth
auth = OpenStreetMapAuth(
    client_id='VOTRE_CLIENT_ID',
    client_secret='VOTRE_CLIENT_SECRET',
    scopes=['read_prefs', 'write_map']
).auth_code()
print('Access token:', auth.token['access_token'])
"
```

### Étape 3 — Variables d'environnement

```bash
export OSM_CLIENT_ID="votre_client_id"
export OSM_CLIENT_SECRET="votre_client_secret"
export OSM_ACCESS_TOKEN="votre_access_token"
```

Ou créez un fichier `.env` (jamais committé) :
```
OSM_CLIENT_ID=...
OSM_CLIENT_SECRET=...
OSM_ACCESS_TOKEN=...
```

---

## 📊 Utilisation

### 1. Analyser l'état actuel de la Guadeloupe sur OSM

```bash
python scripts/analyze.py
```

Génère un rapport complet : ancienneté des données, taux de couverture, recommandations.

### 2. Lister les couches disponibles dans la BD TOPO®

```bash
python scripts/gwadabot.py --theme TRANSPORT --list-layers
```

### 3. Tester en mode dry-run (serveur de développement OSM)

```bash
# Routes
python scripts/gwadabot.py --theme TRANSPORT --dry-run

# Hydrographie
python scripts/gwadabot.py --theme HYDROGRAPHIE --dry-run

# Bâtiments
python scripts/gwadabot.py --theme BATI --dry-run
```

Les fichiers `.osc` sont générés dans `logs/` pour inspection dans JOSM.

### 4. Inspecter les .osc dans JOSM avant upload

```
JOSM → Fichier → Ouvrir → logs/batch_0001.osc
```

Vérifiez visuellement un échantillon avant de lancer en production.

### 5. Lancer en production (après validation communautaire)

```bash
python scripts/gwadabot.py --theme TRANSPORT --production
```

> ⚠️ **Demande une confirmation manuelle.** Ne jamais lancer sans avoir posté
> sur `imports@openstreetmap.org` et reçu l'aval de la communauté.

---

## 📋 Procédure officielle OSM (obligatoire)

Avant tout import en production :

1. **Poster sur** [imports@openstreetmap.org](mailto:imports@openstreetmap.org)
   avec le sujet : `[Import] Guadeloupe — BD TOPO® IGN`

2. **Créer la page wiki** : copier `wiki/WIKI_OSM_PAGE.md` sur
   [wiki.openstreetmap.org/wiki/Import/GwadaBot](https://wiki.openstreetmap.org/wiki/Import/GwadaBot)

3. **Attendre 2 semaines** pour les retours de la communauté

4. **Tester sur** [api06.dev.openstreetmap.org](https://api06.dev.openstreetmap.org)
   et partager les résultats

5. Seulement ensuite → production 🚀

---

## 🗺️ Données sources

| Thème          | Couche BD TOPO®      | Objets estimés | Tags OSM générés          |
|----------------|----------------------|----------------|---------------------------|
| TRANSPORT      | TRONCON_DE_ROUTE     | ~80 000        | highway, maxspeed, oneway |
| HYDROGRAPHIE   | COURS_D_EAU          | ~15 000        | waterway, name            |
| BATI           | BATIMENT             | ~120 000       | building, height          |
| ADMINISTRATIF  | COMMUNE              | ~32             | boundary=administrative   |

**Téléchargement automatique** depuis la Géoplateforme IGN :
```
https://data.geopf.fr/telechargement/download/BDTOPO/
```

---

## ⚙️ Limites respectées

| Paramètre            | Valeur    | Limite OSM |
|----------------------|-----------|------------|
| Objets par changeset | 500       | 10 000     |
| Délai entre batches  | 2 sec     | 0 sec      |
| Objets par jour      | 50 000    | illimité   |

---

## 🏷️ Tags de changeset

Chaque changeset est taggé avec :

```xml
comment    = "GwadaBot — Mise à jour Guadeloupe depuis BD TOPO® IGN"
source     = "IGN BD TOPO® — Licence Ouverte Etalab 2.0"
bot        = "yes"
import     = "yes"
created_by = "GwadaBot/1.0"
url        = "https://wiki.openstreetmap.org/wiki/Import/GwadaBot"
```

---

## 🤝 Contribuer

1. Fork ce repo
2. Améliore la conflation ou ajoute un nouveau thème
3. Ouvre une PR

---

## 📄 Licence

- **Code** : MIT
- **Données produites** : ODbL (hérité d'OSM)
- **Source** : IGN BD TOPO® — Licence Ouverte Etalab 2.0

---

*Fait avec ❤️ pour la Guadeloupe 🌺*
