# GwadaBot

**Import automatisé OpenStreetMap pour la Guadeloupe (971) — BD TOPO IGN**

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://python.org)
[![Licence Ouverte 2.0](https://img.shields.io/badge/source-Licence%20Ouverte%202.0-green.svg)](https://www.etalab.gouv.fr/licence-ouverte-open-licence)
[![ODbL Compatible](https://img.shields.io/badge/ODbL-compatible-brightgreen.svg)](https://opendatacommons.org/licenses/odbl/)
[![OSM Import](https://img.shields.io/badge/wiki-Import%2FGwadaBot-orange.svg)](https://wiki.openstreetmap.org/wiki/Import/GwadaBot)

---

## Contexte

La couverture OpenStreetMap de la Guadeloupe est significativement incomplète. L'IGN BD TOPO recense 379 503 bâtiments sur le territoire ; OSM en compte moins de 50 000. Les cours d'eau, infrastructures sportives, réservoirs et zones de végétation sont largement absents.

GwadaBot exploite la BD TOPO IGN (Licence Ouverte Etalab 2.0, compatible ODbL) pour combler ces lacunes, avec conflation spatiale automatique contre les données OSM existantes.

## Périmètre

| Couche BD TOPO | Objets | Tags OSM |
|---|---|---|
| `batiment` | 379 503 | `building`, `height`, `building:levels`, `building:flats` |
| `troncon_de_route` | 72 695 | `highway`, `maxspeed`, `oneway`, `lanes`, `width`, `surface` |
| `zone_de_vegetation` | 66 970 | `natural=wood`, `landuse`, `wetland=mangrove`, `crop=sugarcane` |
| `troncon_hydrographique` | 16 796 | `waterway`, `name`, `intermittent` |
| `terrain_de_sport` | 747 | `leisure=pitch`, `sport` |
| `pylone` | 662 | `power=tower`, `height` |
| `reservoir` | 418 | `man_made=reservoir` |
| `equipement_de_transport` | 384 | `amenity`, `aeroway` |
| `plan_d_eau` | 71 | `natural=water`, `water` |
| `construction_surfacique` | 56 | divers |
| `cimetiere` | 50 | `landuse=cemetery` |
| `commune` | 32 | `boundary=administrative`, `ref:INSEE` |
| `ligne_electrique` | 28 | `power=line`, `voltage` |
| `aerodrome` | 9 | `aeroway=aerodrome`, `icao`, `iata` |
| **Total** | **~538 000** | |

Source : IGN BD TOPO v3.5, millésime 2025-12-15. Sept millésimes disponibles (2021-03 à 2025-12).

## Architecture

```
scripts/
  gwadabot.py        Pipeline principal — 14 couches, multi-millésimes, génération .osc
  conflation.py      Conflation spatiale STRtree + Overpass (parallélisé par sous-zones)
  analyze.py         Analyse Overpass de l'état OSM Guadeloupe
  osm_auth.py        Authentification OAuth 2.0
```

## Installation

```bash
git clone https://github.com/MaxLananas/gwadabot
cd gwadabot
python -m venv .venv && .venv\Scripts\activate   # Windows
pip install -r requirements.txt
```

Prérequis :
- Python 3.10+
- BD TOPO Guadeloupe (GeoPackage) depuis [data.geopf.fr](https://data.geopf.fr/telechargement/) — département 971

## Configuration

```bash
python scripts/osm_auth.py
```

Génère automatiquement le fichier `.env` (non versionné) :

```
OSM_CLIENT_ID=...
OSM_CLIENT_SECRET=...
OSM_ACCESS_TOKEN=...
```

## Utilisation

### Commandes principales

```bash
# Analyse de l'état OSM actuel
python scripts/analyze.py

# Lister les millésimes disponibles
python scripts/gwadabot.py --list-millesimes

# Comparer l'évolution d'une couche entre millésimes
python scripts/gwadabot.py --compare batiment

# Lister les couches du GeoPackage
python scripts/gwadabot.py --list-layers

# Dry-run — génération .osc sans envoi (serveur dev OSM)
python scripts/gwadabot.py --theme BATI --dry-run
python scripts/gwadabot.py --all --dry-run

# Dry-run avec conflation contre OSM existant
python scripts/gwadabot.py --theme BATI --dry-run --conflation

# Dry-run sur un millésime spécifique
python scripts/gwadabot.py --theme BATI --millesime 2023-12-15 --dry-run

# Ajuster le nombre de batches échantillons
python scripts/gwadabot.py --theme BATI --dry-run --sample 10

# Production (requiert validation communautaire préalable)
python scripts/gwadabot.py --theme BATI --production --conflation
```

### Inspection des résultats

Les fichiers `.osc` sont générés dans `logs/<theme>_<millesime>/` et peuvent être ouverts dans JOSM pour vérification visuelle avant tout envoi.

## Conflation

Chaque élément IGN est comparé spatialement aux données OSM existantes via Overpass API :

| Distance | Action |
|---|---|
| < 10 m | Skip, ou mise à jour des tags si différence détectée |
| 10–50 m | Mise à jour de la géométrie et des tags |
| > 50 m | Création d'un nouvel objet |

Les tags communautaires (`name`, `wikipedia`, `wikidata`, `website`, `opening_hours`) sont systématiquement préservés. Les tags physiques (`highway`, `building`, `height`, `maxspeed`) sont mis à jour depuis la source IGN.

La recherche spatiale utilise un STRtree (R-tree) pour des requêtes en O(log n). L'interrogation Overpass est parallélisée sur 16 sous-zones avec 4 threads.

## Paramètres d'import

| Paramètre | Valeur |
|---|---|
| Objets par changeset | 500 |
| Délai inter-changeset | 2 s |
| Limite quotidienne | 50 000 objets |

Tags de changeset :

```
comment    = "GwadaBot -- Import Guadeloupe depuis BD TOPO IGN"
source     = "IGN BD TOPO 2025-12-15 -- Licence Ouverte Etalab 2.0"
bot        = "yes"
import     = "yes"
created_by = "GwadaBot/2.0"
```

## Validation communautaire

Conformément aux [Import Guidelines](https://wiki.openstreetmap.org/wiki/Import/Guidelines), l'import est soumis à validation :

- [x] Page wiki : [Import/GwadaBot](https://wiki.openstreetmap.org/wiki/Import/GwadaBot)
- [x] Proposition envoyée à [imports@openstreetmap.org](mailto:imports@openstreetmap.org)
- [x] Discussion sur [talk-fr@openstreetmap.org](mailto:talk-fr@openstreetmap.org)
- [x] Sujet ouvert sur [forum.openstreetmap.fr](https://forum.openstreetmap.fr/)
- [ ] Période de review communautaire
- [ ] Intégration des retours
- [ ] Feu vert communautaire

Aucun envoi en production ne sera effectué sans accord explicite de la communauté.

## Licence

- **Code** : MIT
- **Données produites** : ODbL (hérité d'OpenStreetMap)
- **Source** : IGN BD TOPO — [Licence Ouverte Etalab 2.0](https://www.etalab.gouv.fr/licence-ouverte-open-licence)
