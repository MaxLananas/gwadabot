# 🌴 GwadaBot v2.0

> **Bot d'import OSM pour la Guadeloupe** — Powered by IGN BD TOPO® 2025

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://python.org)
[![Licence Ouverte 2.0](https://img.shields.io/badge/source-Licence%20Ouverte%202.0-green.svg)](https://www.etalab.gouv.fr/licence-ouverte-open-licence)
[![ODbL Compatible](https://img.shields.io/badge/ODbL-compatible-brightgreen.svg)](https://opendatacommons.org/licenses/odbl/)
[![OSM Import](https://img.shields.io/badge/OSM-import-orange.svg)](https://wiki.openstreetmap.org/wiki/Import/GwadaBot)

---

La Guadeloupe est l'un des territoires français les **moins bien couverts sur OpenStreetMap** :
moins de 50 000 bâtiments cartographiés, alors que l'IGN en recense **379 503**.

**GwadaBot** importe proprement les données de la BD TOPO® IGN — la référence topographique
officielle de la France à précision métrique — avec conflation automatique contre l'existant OSM.

```
╔═══════════════════════════════════════════════════════╗
║  IGN BD TOPO® 2025 → Conflation → OSM 🗺️            ║
║  14 couches · 538 000 objets · 7 millésimes (2021-25)║
║  Bâtiments · Routes · Hydro · Végétation · Énergie   ║
╚═══════════════════════════════════════════════════════╝
```

---

## 📊 Données importées

| Thème | Couche BD TOPO | Objets | Tags OSM |
|---|---|---|---|
| 🏠 Bâtiments | `batiment` | 379 503 | `building`, `height`, `building:levels`, `building:flats` |
| 🛣️ Routes | `troncon_de_route` | 72 695 | `highway`, `maxspeed`, `oneway`, `lanes`, `width`, `surface` |
| 🌊 Hydrographie | `troncon_hydrographique` | 16 796 | `waterway`, `name`, `intermittent` |
| 💧 Plans d'eau | `plan_d_eau` | 71 | `natural=water`, `water` |
| ⚽ Sport | `terrain_de_sport` | 747 | `leisure=pitch`, `sport` |
| ⚰️ Cimetières | `cimetiere` | 50 | `landuse=cemetery` |
| 🏗️ Réservoirs | `reservoir` | 418 | `man_made=reservoir` |
| 🌴 Végétation | `zone_de_vegetation` | 66 970 | `natural=wood`, `landuse`, `wetland=mangrove`, `crop=sugarcane` |
| ⚡ Pylônes | `pylone` | 662 | `power=tower`, `height` |
| ⚡ Lignes élec. | `ligne_electrique` | 28 | `power=line`, `voltage` |
| ✈️ Aérodromes | `aerodrome` | 9 | `aeroway`, `icao`, `iata` |
| 🚏 Équipements | `equipement_de_transport` | 384 | `amenity`, `aeroway` |
| 🏗️ Constructions | `construction_surfacique` | 56 | divers |
| 🏛️ Communes | `commune` | 32 | `boundary=administrative`, `ref:INSEE` |
| **TOTAL** | | **~538 000** | |

---

## 📦 Structure du projet

```
OSM-GwadaBot/
├── scripts/
│   ├── gwadabot.py          ← Bot principal (14 couches, multi-millésimes)
│   ├── conflation.py        ← Moteur de conflation STRtree + Overpass
│   ├── analyze.py           ← Analyse de l'état OSM Guadeloupe
│   └── osm_auth.py          ← Authentification OAuth2
├── BDTOPO_*_D971_*/         ← BD TOPO téléchargées (gitignored)
├── logs/                    ← Fichiers .osc + stats JSON (par thème)
│   ├── bati_2025-12-15/
│   ├── transport_2025-12-15/
│   └── stats_*.json
├── WIKI_OSM_PAGE.md
├── requirements.txt
├── .gitignore
└── README.md
```

---

## 🚀 Installation

```bash
git clone https://github.com/MaxLananas/gwadabot
cd gwadabot

python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/Mac:
source .venv/bin/activate

pip install -r requirements.txt
```

### Prérequis

- Python 3.10+
- BD TOPO Guadeloupe téléchargée depuis [data.geopf.fr](https://data.geopf.fr/telechargement/)
  (chercher "BD TOPO" → département 971 → GeoPackage)

---

## 🔐 Authentification OSM (OAuth 2.0)

```bash
python scripts/osm_auth.py
```

Suivez les instructions. Le script crée automatiquement le fichier `.env` avec vos credentials.

Ou manuellement, créez `.env` à la racine :
```
OSM_CLIENT_ID=votre_id
OSM_CLIENT_SECRET=votre_secret
OSM_ACCESS_TOKEN=votre_token
```

> ⚠️ Ne committez **jamais** le fichier `.env`

---

## 📊 Utilisation

### Analyser l'état actuel d'OSM en Guadeloupe

```bash
python scripts/analyze.py
```

### Lister les millésimes BD TOPO disponibles

```bash
python scripts/gwadabot.py --list-millesimes
```
```
  Millesimes BD TOPO D971 (7) :
    2021-03-15  ->  BDT_3-0_GPKG_RGAF09UTM20_D971-ED2021-03-15.gpkg
    2023-12-15  ->  BDT_3-3_GPKG_RGAF09UTM20_D971-ED2023-12-15.gpkg
    2024-03-15  ->  BDT_3-3_GPKG_RGAF09UTM20_D971-ED2024-03-15.gpkg
    2025-03-15  ->  BDT_3-4_GPKG_RGAF09UTM20_D971-ED2025-03-15.gpkg
    2025-06-15  ->  BDT_3-5_GPKG_RGAF09UTM20_D971-ED2025-06-15.gpkg
    2025-09-15  ->  BDT_3-5_GPKG_RGAF09UTM20_D971-ED2025-09-15.gpkg
    2025-12-15  ->  BDT_3-5_GPKG_RGAF09UTM20_D971-ED2025-12-15.gpkg
```

### Comparer l'évolution entre millésimes

```bash
python scripts/gwadabot.py --compare batiment
```
```
  2021-03-15 :    382,692 objets
  2023-12-15 :    380,637 objets  (-2,055)
  2025-12-15 :    379,503 objets  (-171)
  Evolution totale : -3,189 (2021-03-15 -> 2025-12-15)
```

### Lister les couches disponibles

```bash
python scripts/gwadabot.py --list-layers
```

### Dry-run (serveur de développement OSM)

```bash
# Un seul thème
python scripts/gwadabot.py --theme BATI --dry-run

# Tous les thèmes
python scripts/gwadabot.py --all --dry-run

# Avec conflation (compare avec OSM existant)
python scripts/gwadabot.py --theme BATI --dry-run --conflation

# Plus de batches échantillons
python scripts/gwadabot.py --theme BATI --dry-run --sample 10

# Utiliser un ancien millésime
python scripts/gwadabot.py --theme BATI --millesime 2023-12-15 --dry-run
```

Les fichiers `.osc` sont générés dans `logs/<theme>_<millesime>/` pour inspection dans JOSM.

### Inspecter dans JOSM

```
JOSM → Fichier → Ouvrir → logs/bati_2025-12-15/batch_0001.osc
```

### Production (après validation communautaire uniquement)

```bash
python scripts/gwadabot.py --theme BATI --production --conflation
```

> ⚠️ **Ne jamais lancer `--production` sans avoir posté sur `imports@openstreetmap.org`
> et attendu minimum 2 semaines de retours communautaires.**

---

## 🔄 Conflation

Le bot compare chaque élément IGN avec les données OSM existantes via Overpass :

| Distance IGN ↔ OSM | Action |
|---|---|
| < 10 m | **Skip** ou mise à jour des tags uniquement |
| 10–50 m | **Update** géométrie + tags (objet déplacé) |
| > 50 m | **Création** nouvel objet |

**Priorité des tags :**
- IGN gagne sur : `highway`, `building`, `waterway`, `maxspeed`, `height`, `surface`...
- OSM gagne sur : `name`, `wikipedia`, `wikidata`, `website`, `opening_hours`...

---

## ⚙️ Limites respectées

| Paramètre | Valeur | Limite OSM |
|---|---|---|
| Objets par changeset | 500 | 10 000 |
| Délai entre changesets | 2 sec | aucune |
| Objets par jour | 50 000 | illimitée |

---

## 🏷️ Tags de changeset

```xml
comment    = "GwadaBot -- Import Guadeloupe depuis BD TOPO IGN"
source     = "IGN BD TOPO 2025-12-15 -- Licence Ouverte Etalab 2.0"
bot        = "yes"
import     = "yes"
created_by = "GwadaBot/2.0"
url        = "https://wiki.openstreetmap.org/wiki/Import/GwadaBot"
```

---

## 📋 Procédure officielle OSM (obligatoire)

Avant tout import en production :

1. ✅ **Page wiki créée** : [wiki.openstreetmap.org/wiki/Import/GwadaBot](https://wiki.openstreetmap.org/wiki/Import/GwadaBot)
2. ⬜ **Email à** [imports@openstreetmap.org](mailto:imports@openstreetmap.org)
3. ⬜ **Email à** [talk-fr@openstreetmap.org](mailto:talk-fr@openstreetmap.org)
4. ⬜ **Attendre 2 semaines** minimum
5. ⬜ **Partager les résultats** dry-run + screenshots JOSM
6. ⬜ **Intégrer les retours** communautaires
7. ⬜ **Recevoir le feu vert** → production 🚀

---

## 🤝 Contribuer

1. Fork ce repo
2. Améliore la conflation, ajoute un thème, corrige un mapping
3. Ouvre une PR

---

## 📄 Licence

- **Code** : MIT
- **Données produites** : ODbL (hérité d'OSM)
- **Source** : IGN BD TOPO® — [Licence Ouverte Etalab 2.0](https://www.etalab.gouv.fr/licence-ouverte-open-licence)

---

*Fait avec ❤️ pour la Guadeloupe 🌺*
